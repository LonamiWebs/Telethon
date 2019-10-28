"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like a User, Chat, etc. into its Input version)
"""
import base64
import binascii
import imghdr
import inspect
import io
import itertools
import logging
import math
import mimetypes
import os
import re
import struct
from mimetypes import guess_extension
from types import GeneratorType

from .extensions import markdown, html
from .helpers import add_surrogate, del_surrogate
from .tl import types

try:
    import hachoir
    import hachoir.metadata
    import hachoir.parser
except ImportError:
    hachoir = None

# Register some of the most common mime-types to avoid any issues.
# See https://github.com/LonamiWebs/Telethon/issues/1096.
mimetypes.add_type('image/png', '.png')
mimetypes.add_type('image/jpeg', '.jpeg')
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/gif', '.gif')
mimetypes.add_type('image/bmp', '.bmp')
mimetypes.add_type('image/x-tga', '.tga')
mimetypes.add_type('image/tiff', '.tiff')
mimetypes.add_type('image/vnd.adobe.photoshop', '.psd')

mimetypes.add_type('video/mp4', '.mp4')
mimetypes.add_type('video/quicktime', '.mov')
mimetypes.add_type('video/avi', '.avi')

mimetypes.add_type('audio/mpeg', '.mp3')
mimetypes.add_type('audio/m4a', '.m4a')
mimetypes.add_type('audio/aac', '.aac')
mimetypes.add_type('audio/ogg', '.ogg')
mimetypes.add_type('audio/flac', '.flac')

USERNAME_RE = re.compile(
    r'@|(?:https?://)?(?:www\.)?(?:telegram\.(?:me|dog)|t\.me)/(@|joinchat/)?'
)
TG_JOIN_RE = re.compile(
    r'tg://(join)\?invite='
)

# The only shorter-than-five-characters usernames are those used for some
# special, very well known bots. This list may be incomplete though:
#    "[...] @gif, @vid, @pic, @bing, @wiki, @imdb and @bold [...]"
#
# See https://telegram.org/blog/inline-bots#how-does-it-work
VALID_USERNAME_RE = re.compile(
    r'^([a-z]((?!__)[\w\d]){3,30}[a-z\d]'
    r'|gif|vid|pic|bing|wiki|imdb|bold|vote|like|coub)$',
    re.IGNORECASE
)

_log = logging.getLogger(__name__)


def chunks(iterable, size=100):
    """
    Turns the given iterable into chunks of the specified size,
    which is 100 by default since that's what Telegram uses the most.
    """
    it = iter(iterable)
    size -= 1
    for head in it:
        yield itertools.chain([head], itertools.islice(it, size))


def get_display_name(entity):
    """
    Gets the display name for the given :tl:`User`,
    :tl:`Chat` or :tl:`Channel`. Returns an empty string otherwise.
    """
    if isinstance(entity, types.User):
        if entity.last_name and entity.first_name:
            return '{} {}'.format(entity.first_name, entity.last_name)
        elif entity.first_name:
            return entity.first_name
        elif entity.last_name:
            return entity.last_name
        else:
            return ''

    elif isinstance(entity, (types.Chat, types.Channel)):
        return entity.title

    return ''


def get_extension(media):
    """Gets the corresponding extension for any Telegram media."""

    # Photos are always compressed as .jpg by Telegram
    try:
        get_input_photo(media)
        return '.jpg'
    except TypeError:
        # These cases are not handled by input photo because it can't
        if isinstance(media, (types.UserProfilePhoto, types.ChatPhoto)):
            return '.jpg'

    # Documents will come with a mime type
    if isinstance(media, types.MessageMediaDocument):
        media = media.document
    if isinstance(media, (
            types.Document, types.WebDocument, types.WebDocumentNoProxy)):
        if media.mime_type == 'application/octet-stream':
            # Octet stream are just bytes, which have no default extension
            return ''
        else:
            return guess_extension(media.mime_type) or ''

    return ''


def _raise_cast_fail(entity, target):
    raise TypeError('Cannot cast {} to any kind of {}.'.format(
        type(entity).__name__, target))


def get_input_peer(entity, allow_self=True, check_hash=True):
    """
    Gets the input peer for the given "entity" (user, chat or channel).

    A ``TypeError`` is raised if the given entity isn't a supported type
    or if ``check_hash is True`` but the entity's ``access_hash is None``
    *or* the entity contains ``min`` information. In this case, the hash
    cannot be used for general purposes, and thus is not returned to avoid
    any issues which can derive from invalid access hashes.

    Note that ``check_hash`` **is ignored** if an input peer is already
    passed since in that case we assume the user knows what they're doing.
    This is key to getting entities by explicitly passing ``hash = 0``.
    """
    # NOTE: It is important that this method validates the access hashes,
    #       because it is used when we *require* a valid general-purpose
    #       access hash. This includes caching, which relies on this method.
    #       Further, when resolving raw methods, they do e.g.,
    #           utils.get_input_channel(client.get_input_peer(...))
    #
    #       ...which means that the client's method verifies the hashes.
    #
    # Excerpt from a conversation with official developers (slightly edited):
    #     > We send new access_hash for Channel with min flag since layer 102.
    #     > Previously, we omitted it.
    #     > That one works just to download the profile picture.
    #
    #     < So, min hashes only work for getting files,
    #     < but the non-min hash is required for any other operation?
    #
    #     > Yes.
    #
    # More information: https://core.telegram.org/api/min
    try:
        if entity.SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
            return entity
    except AttributeError:
        # e.g. custom.Dialog (can't cyclic import).
        if allow_self and hasattr(entity, 'input_entity'):
            return entity.input_entity
        elif hasattr(entity, 'entity'):
            return get_input_peer(entity.entity)
        else:
            _raise_cast_fail(entity, 'InputPeer')

    if isinstance(entity, types.User):
        if entity.is_self and allow_self:
            return types.InputPeerSelf()
        elif (entity.access_hash is not None and not entity.min) or not check_hash:
            return types.InputPeerUser(entity.id, entity.access_hash)
        else:
            raise TypeError('User without access_hash or min info cannot be input')

    if isinstance(entity, (types.Chat, types.ChatEmpty, types.ChatForbidden)):
        return types.InputPeerChat(entity.id)

    if isinstance(entity, types.Channel):
        if (entity.access_hash is not None and not entity.min) or not check_hash:
            return types.InputPeerChannel(entity.id, entity.access_hash)
        else:
            raise TypeError('Channel without access_hash or min info cannot be input')
    if isinstance(entity, types.ChannelForbidden):
        # "channelForbidden are never min", and since their hash is
        # also not optional, we assume that this truly is the case.
        return types.InputPeerChannel(entity.id, entity.access_hash)

    if isinstance(entity, types.InputUser):
        return types.InputPeerUser(entity.user_id, entity.access_hash)

    if isinstance(entity, types.InputChannel):
        return types.InputPeerChannel(entity.channel_id, entity.access_hash)

    if isinstance(entity, types.InputUserSelf):
        return types.InputPeerSelf()

    if isinstance(entity, types.UserEmpty):
        return types.InputPeerEmpty()

    if isinstance(entity, types.UserFull):
        return get_input_peer(entity.user)

    if isinstance(entity, types.ChatFull):
        return types.InputPeerChat(entity.id)

    if isinstance(entity, types.PeerChat):
        return types.InputPeerChat(entity.chat_id)

    _raise_cast_fail(entity, 'InputPeer')


def get_input_channel(entity):
    """
    Similar to :meth:`get_input_peer`, but for :tl:`InputChannel`'s alone.

    .. important::

        This method does not validate for invalid general-purpose access
        hashes, unlike `get_input_peer`. Consider using instead:
        ``get_input_channel(get_input_peer(channel))``.
    """
    try:
        if entity.SUBCLASS_OF_ID == 0x40f202fd:  # crc32(b'InputChannel')
            return entity
    except AttributeError:
        _raise_cast_fail(entity, 'InputChannel')

    if isinstance(entity, (types.Channel, types.ChannelForbidden)):
        return types.InputChannel(entity.id, entity.access_hash or 0)

    if isinstance(entity, types.InputPeerChannel):
        return types.InputChannel(entity.channel_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputChannel')


def get_input_user(entity):
    """
    Similar to :meth:`get_input_peer`, but for :tl:`InputUser`'s alone.

    .. important::

        This method does not validate for invalid general-purpose access
        hashes, unlike `get_input_peer`. Consider using instead:
        ``get_input_channel(get_input_peer(channel))``.
    """
    try:
        if entity.SUBCLASS_OF_ID == 0xe669bf46:  # crc32(b'InputUser'):
            return entity
    except AttributeError:
        _raise_cast_fail(entity, 'InputUser')

    if isinstance(entity, types.User):
        if entity.is_self:
            return types.InputUserSelf()
        else:
            return types.InputUser(entity.id, entity.access_hash or 0)

    if isinstance(entity, types.InputPeerSelf):
        return types.InputUserSelf()

    if isinstance(entity, (types.UserEmpty, types.InputPeerEmpty)):
        return types.InputUserEmpty()

    if isinstance(entity, types.UserFull):
        return get_input_user(entity.user)

    if isinstance(entity, types.InputPeerUser):
        return types.InputUser(entity.user_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputUser')


def get_input_dialog(dialog):
    """Similar to :meth:`get_input_peer`, but for dialogs"""
    try:
        if dialog.SUBCLASS_OF_ID == 0xa21c9795:  # crc32(b'InputDialogPeer')
            return dialog
        if dialog.SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
            return types.InputDialogPeer(dialog)
    except AttributeError:
        _raise_cast_fail(dialog, 'InputDialogPeer')

    try:
        return types.InputDialogPeer(get_input_peer(dialog))
    except TypeError:
        pass

    _raise_cast_fail(dialog, 'InputDialogPeer')


def get_input_document(document):
    """Similar to :meth:`get_input_peer`, but for documents"""
    try:
        if document.SUBCLASS_OF_ID == 0xf33fdb68:  # crc32(b'InputDocument'):
            return document
    except AttributeError:
        _raise_cast_fail(document, 'InputDocument')

    if isinstance(document, types.Document):
        return types.InputDocument(
            id=document.id, access_hash=document.access_hash,
            file_reference=document.file_reference)

    if isinstance(document, types.DocumentEmpty):
        return types.InputDocumentEmpty()

    if isinstance(document, types.MessageMediaDocument):
        return get_input_document(document.document)

    if isinstance(document, types.Message):
        return get_input_document(document.media)

    _raise_cast_fail(document, 'InputDocument')


def get_input_photo(photo):
    """Similar to :meth:`get_input_peer`, but for photos"""
    try:
        if photo.SUBCLASS_OF_ID == 0x846363e0:  # crc32(b'InputPhoto'):
            return photo
    except AttributeError:
        _raise_cast_fail(photo, 'InputPhoto')

    if isinstance(photo, types.Message):
        photo = photo.media

    if isinstance(photo, (types.photos.Photo, types.MessageMediaPhoto)):
        photo = photo.photo

    if isinstance(photo, types.Photo):
        return types.InputPhoto(id=photo.id, access_hash=photo.access_hash,
                                file_reference=photo.file_reference)

    if isinstance(photo, types.PhotoEmpty):
        return types.InputPhotoEmpty()

    if isinstance(photo, types.messages.ChatFull):
        photo = photo.full_chat

    if isinstance(photo, types.ChannelFull):
        return get_input_photo(photo.chat_photo)
    elif isinstance(photo, types.UserFull):
        return get_input_photo(photo.profile_photo)
    elif isinstance(photo, (types.Channel, types.Chat, types.User)):
        return get_input_photo(photo.photo)

    if isinstance(photo, (types.UserEmpty, types.ChatEmpty,
                          types.ChatForbidden, types.ChannelForbidden)):
        return types.InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


def get_input_chat_photo(photo):
    """Similar to :meth:`get_input_peer`, but for chat photos"""
    try:
        if photo.SUBCLASS_OF_ID == 0xd4eb2d74:  # crc32(b'InputChatPhoto')
            return photo
        elif photo.SUBCLASS_OF_ID == 0xe7655f1f:  # crc32(b'InputFile'):
            return types.InputChatUploadedPhoto(photo)
    except AttributeError:
        _raise_cast_fail(photo, 'InputChatPhoto')

    photo = get_input_photo(photo)
    if isinstance(photo, types.InputPhoto):
        return types.InputChatPhoto(photo)
    elif isinstance(photo, types.InputPhotoEmpty):
        return types.InputChatPhotoEmpty()

    _raise_cast_fail(photo, 'InputChatPhoto')


def get_input_geo(geo):
    """Similar to :meth:`get_input_peer`, but for geo points"""
    try:
        if geo.SUBCLASS_OF_ID == 0x430d225:  # crc32(b'InputGeoPoint'):
            return geo
    except AttributeError:
        _raise_cast_fail(geo, 'InputGeoPoint')

    if isinstance(geo, types.GeoPoint):
        return types.InputGeoPoint(lat=geo.lat, long=geo.long)

    if isinstance(geo, types.GeoPointEmpty):
        return types.InputGeoPointEmpty()

    if isinstance(geo, types.MessageMediaGeo):
        return get_input_geo(geo.geo)

    if isinstance(geo, types.Message):
        return get_input_geo(geo.media)

    _raise_cast_fail(geo, 'InputGeoPoint')


def get_input_media(
        media, *,
        is_photo=False, attributes=None, force_document=False,
        voice_note=False, video_note=False, supports_streaming=False
):
    """
    Similar to :meth:`get_input_peer`, but for media.

    If the media is :tl:`InputFile` and ``is_photo`` is known to be `True`,
    it will be treated as an :tl:`InputMediaUploadedPhoto`. Else, the rest
    of parameters will indicate how to treat it.
    """
    try:
        if media.SUBCLASS_OF_ID == 0xfaf846f4:  # crc32(b'InputMedia')
            return media
        elif media.SUBCLASS_OF_ID == 0x846363e0:  # crc32(b'InputPhoto')
            return types.InputMediaPhoto(media)
        elif media.SUBCLASS_OF_ID == 0xf33fdb68:  # crc32(b'InputDocument')
            return types.InputMediaDocument(media)
    except AttributeError:
        _raise_cast_fail(media, 'InputMedia')

    if isinstance(media, types.MessageMediaPhoto):
        return types.InputMediaPhoto(
            id=get_input_photo(media.photo),
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, (types.Photo, types.photos.Photo, types.PhotoEmpty)):
        return types.InputMediaPhoto(
            id=get_input_photo(media)
        )

    if isinstance(media, types.MessageMediaDocument):
        return types.InputMediaDocument(
            id=get_input_document(media.document),
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, (types.Document, types.DocumentEmpty)):
        return types.InputMediaDocument(
            id=get_input_document(media)
        )

    if isinstance(media, (types.InputFile, types.InputFileBig)):
        if is_photo:
            return types.InputMediaUploadedPhoto(file=media)
        else:
            attrs, mime = get_attributes(
                media,
                attributes=attributes,
                force_document=force_document,
                voice_note=voice_note,
                video_note=video_note,
                supports_streaming=supports_streaming
            )
            return types.InputMediaUploadedDocument(
                file=media, mime_type=mime, attributes=attrs)

    if isinstance(media, types.MessageMediaGame):
        return types.InputMediaGame(id=media.game.id)

    if isinstance(media, types.MessageMediaContact):
        return types.InputMediaContact(
            phone_number=media.phone_number,
            first_name=media.first_name,
            last_name=media.last_name,
            vcard=''
        )

    if isinstance(media, types.MessageMediaGeo):
        return types.InputMediaGeoPoint(geo_point=get_input_geo(media.geo))

    if isinstance(media, types.MessageMediaVenue):
        return types.InputMediaVenue(
            geo_point=get_input_geo(media.geo),
            title=media.title,
            address=media.address,
            provider=media.provider,
            venue_id=media.venue_id,
            venue_type=''
        )

    if isinstance(media, (
            types.MessageMediaEmpty, types.MessageMediaUnsupported,
            types.ChatPhotoEmpty, types.UserProfilePhotoEmpty,
            types.ChatPhoto, types.UserProfilePhoto,
            types.FileLocationToBeDeprecated)):
        return types.InputMediaEmpty()

    if isinstance(media, types.Message):
        return get_input_media(media.media, is_photo=is_photo)

    _raise_cast_fail(media, 'InputMedia')


def get_input_message(message):
    """Similar to :meth:`get_input_peer`, but for input messages."""
    try:
        if isinstance(message, int):  # This case is really common too
            return types.InputMessageID(message)
        elif message.SUBCLASS_OF_ID == 0x54b6bcc5:  # crc32(b'InputMessage'):
            return message
        elif message.SUBCLASS_OF_ID == 0x790009e3:  # crc32(b'Message'):
            return types.InputMessageID(message.id)
    except AttributeError:
        pass

    _raise_cast_fail(message, 'InputMedia')


def _get_entity_pair(entity_id, entities, cache,
                     get_input_peer=get_input_peer):
    """
    Returns ``(entity, input_entity)`` for the given entity ID.
    """
    entity = entities.get(entity_id)
    try:
        input_entity = cache[entity_id]
    except KeyError:
        # KeyError is unlikely, so another TypeError won't hurt
        try:
            input_entity = get_input_peer(entity)
        except TypeError:
            input_entity = None

    return entity, input_entity


def get_message_id(message):
    """Similar to :meth:`get_input_peer`, but for message IDs."""
    if message is None:
        return None

    if isinstance(message, int):
        return message

    try:
        if message.SUBCLASS_OF_ID == 0x790009e3:
            # hex(crc32(b'Message')) = 0x790009e3
            return message.id
    except AttributeError:
        pass

    raise TypeError('Invalid message type: {}'.format(type(message)))


def _get_metadata(file):
    # `hachoir` only deals with paths to in-disk files, while
    # `_get_extension` supports a few other things. The parser
    # may also fail in any case and we don't want to crash if
    # the extraction process fails.
    if hachoir and isinstance(file, str) and os.path.isfile(file):
        try:
            with hachoir.parser.createParser(file) as parser:
                return hachoir.metadata.extractMetadata(parser)
        except Exception as e:
            _log.warning('Failed to analyze %s: %s %s', file, e.__class__, e)


def get_attributes(file, *, attributes=None, mime_type=None,
                   force_document=False, voice_note=False, video_note=False,
                   supports_streaming=False):
    """
    Get a list of attributes for the given file and
    the mime type as a tuple ([attribute], mime_type).
    """
    # Note: ``file.name`` works for :tl:`InputFile` and some `IOBase` streams
    name = file if isinstance(file, str) else getattr(file, 'name', 'unnamed')
    if mime_type is None:
        mime_type = mimetypes.guess_type(name)[0]

    attr_dict = {types.DocumentAttributeFilename:
        types.DocumentAttributeFilename(os.path.basename(name))}

    if is_audio(file):
        m = _get_metadata(file)
        if m:
            attr_dict[types.DocumentAttributeAudio] = \
                types.DocumentAttributeAudio(
                    voice=voice_note,
                    title=m.get('title') if m.has('title') else None,
                    performer=m.get('author') if m.has('author') else None,
                    duration=int(m.get('duration').seconds
                                 if m.has('duration') else 0)
                )

    if not force_document and is_video(file):
        m = _get_metadata(file)
        if m:
            doc = types.DocumentAttributeVideo(
                round_message=video_note,
                w=m.get('width') if m.has('width') else 0,
                h=m.get('height') if m.has('height') else 0,
                duration=int(m.get('duration').seconds
                             if m.has('duration') else 0),
                supports_streaming=supports_streaming
            )
        else:
            doc = types.DocumentAttributeVideo(
                0, 1, 1, round_message=video_note,
                supports_streaming=supports_streaming)

        attr_dict[types.DocumentAttributeVideo] = doc

    if voice_note:
        if types.DocumentAttributeAudio in attr_dict:
            attr_dict[types.DocumentAttributeAudio].voice = True
        else:
            attr_dict[types.DocumentAttributeAudio] = \
                types.DocumentAttributeAudio(0, voice=True)

    # Now override the attributes if any. As we have a dict of
    # {cls: instance}, we can override any class with the list
    # of attributes provided by the user easily.
    if attributes:
        for a in attributes:
            attr_dict[type(a)] = a

    # Ensure we have a mime type, any; but it cannot be None
    # 'The "octet-stream" subtype is used to indicate that a body
    # contains arbitrary binary data.'
    if not mime_type:
        mime_type = 'application/octet-stream'

    return list(attr_dict.values()), mime_type


def sanitize_parse_mode(mode):
    """
    Converts the given parse mode into an object with
    ``parse`` and ``unparse`` callable properties.
    """
    if not mode:
        return None

    if callable(mode):
        class CustomMode:
            @staticmethod
            def unparse(text, entities):
                raise NotImplementedError

        CustomMode.parse = mode
        return CustomMode
    elif (all(hasattr(mode, x) for x in ('parse', 'unparse'))
          and all(callable(x) for x in (mode.parse, mode.unparse))):
        return mode
    elif isinstance(mode, str):
        try:
            return {
                'md': markdown,
                'markdown': markdown,
                'htm': html,
                'html': html
            }[mode.lower()]
        except KeyError:
            raise ValueError('Unknown parse mode {}'.format(mode))
    else:
        raise TypeError('Invalid parse mode type {}'.format(mode))


def get_input_location(location):
    """
    Similar to :meth:`get_input_peer`, but for input messages.

    Note that this returns a tuple ``(dc_id, location)``, the
    ``dc_id`` being present if known.
    """
    try:
        if location.SUBCLASS_OF_ID == 0x1523d462:
            return None, location  # crc32(b'InputFileLocation'):
    except AttributeError:
        _raise_cast_fail(location, 'InputFileLocation')

    if isinstance(location, types.Message):
        location = location.media

    if isinstance(location, types.MessageMediaDocument):
        location = location.document
    elif isinstance(location, types.MessageMediaPhoto):
        location = location.photo

    if isinstance(location, types.Document):
        return (location.dc_id, types.InputDocumentFileLocation(
            id=location.id,
            access_hash=location.access_hash,
            file_reference=location.file_reference,
            thumb_size=''  # Presumably to download one of its thumbnails
        ))
    elif isinstance(location, types.Photo):
        return (location.dc_id, types.InputPhotoFileLocation(
            id=location.id,
            access_hash=location.access_hash,
            file_reference=location.file_reference,
            thumb_size=location.sizes[-1].type
        ))

    if isinstance(location, types.FileLocationToBeDeprecated):
        raise TypeError('Unavailable location cannot be used as input')

    _raise_cast_fail(location, 'InputFileLocation')


def _get_extension(file):
    """
    Gets the extension for the given file, which can be either a
    str or an ``open()``'ed file (which has a ``.name`` attribute).
    """
    if isinstance(file, str):
        return os.path.splitext(file)[-1]
    elif isinstance(file, bytes):
        kind = imghdr.what(io.BytesIO(file))
        return ('.' + kind) if kind else ''
    elif isinstance(file, io.IOBase) and file.seekable():
        kind = imghdr.what(file)
        return ('.' + kind) if kind is not None else ''
    elif getattr(file, 'name', None):
        # Note: ``file.name`` works for :tl:`InputFile` and some `IOBase`
        return _get_extension(file.name)
    else:
        # Maybe it's a Telegram media
        return get_extension(file)


def is_image(file):
    """
    Returns `True` if the file extension looks like an image file to Telegram.
    """
    match = re.match(r'\.(png|jpe?g)', _get_extension(file), re.IGNORECASE)
    if match:
        return True
    else:
        return isinstance(resolve_bot_file_id(file), types.Photo)


def is_gif(file):
    """
    Returns `True` if the file extension looks like a gif file to Telegram.
    """
    return re.match(r'\.gif', _get_extension(file), re.IGNORECASE)


def is_audio(file):
    """Returns `True` if the file extension looks like an audio file."""
    file = 'a' + _get_extension(file)
    return (mimetypes.guess_type(file)[0] or '').startswith('audio/')


def is_video(file):
    """Returns `True` if the file extension looks like a video file."""
    file = 'a' + _get_extension(file)
    return (mimetypes.guess_type(file)[0] or '').startswith('video/')


def is_list_like(obj):
    """
    Returns `True` if the given object looks like a list.

    Checking ``if hasattr(obj, '__iter__')`` and ignoring ``str/bytes`` is not
    enough. Things like ``open()`` are also iterable (and probably many
    other things), so just support the commonly known list-like objects.
    """
    return isinstance(obj, (list, tuple, set, dict, GeneratorType))


def parse_phone(phone):
    """Parses the given phone, or returns `None` if it's invalid."""
    if isinstance(phone, int):
        return str(phone)
    else:
        phone = re.sub(r'[+()\s-]', '', str(phone))
        if phone.isdigit():
            return phone


def parse_username(username):
    """
    Parses the given username or channel access hash, given
    a string, username or URL. Returns a tuple consisting of
    both the stripped, lowercase username and whether it is
    a joinchat/ hash (in which case is not lowercase'd).

    Returns ``(None, False)`` if the ``username`` or link is not valid.
    """
    username = username.strip()
    m = USERNAME_RE.match(username) or TG_JOIN_RE.match(username)
    if m:
        username = username[m.end():]
        is_invite = bool(m.group(1))
        if is_invite:
            return username, True
        else:
            username = username.rstrip('/')

    if VALID_USERNAME_RE.match(username):
        return username.lower(), False
    else:
        return None, False


def get_inner_text(text, entities):
    """
    Gets the inner text that's surrounded by the given entities.
    For instance: text = 'hey!', entity = MessageEntityBold(2, 2) -> 'y!'.

    :param text:     the original text.
    :param entities: the entity or entities that must be matched.
    :return: a single result or a list of the text surrounded by the entities.
    """
    text = add_surrogate(text)
    result = []
    for e in entities:
        start = e.offset
        end = e.offset + e.length
        result.append(del_surrogate(text[start:end]))

    return result


def get_peer(peer):
    try:
        if isinstance(peer, int):
            pid, cls = resolve_id(peer)
            return cls(pid)
        elif peer.SUBCLASS_OF_ID == 0x2d45687:
            return peer
        elif isinstance(peer, (
                types.contacts.ResolvedPeer, types.InputNotifyPeer,
                types.TopPeer, types.Dialog, types.DialogPeer)):
            return peer.peer
        elif isinstance(peer, types.ChannelFull):
            return types.PeerChannel(peer.id)

        if peer.SUBCLASS_OF_ID in (0x7d7c6f86, 0xd9c7fc18):
            # ChatParticipant, ChannelParticipant
            return types.PeerUser(peer.user_id)

        peer = get_input_peer(peer, allow_self=False, check_hash=False)
        if isinstance(peer, types.InputPeerUser):
            return types.PeerUser(peer.user_id)
        elif isinstance(peer, types.InputPeerChat):
            return types.PeerChat(peer.chat_id)
        elif isinstance(peer, types.InputPeerChannel):
            return types.PeerChannel(peer.channel_id)
    except (AttributeError, TypeError):
        pass
    _raise_cast_fail(peer, 'Peer')


def get_peer_id(peer, add_mark=True):
    """
    Convert the given peer into its marked ID by default.

    This "mark" comes from the "bot api" format, and with it the peer type
    can be identified back. User ID is left unmodified, chat ID is negated,
    and channel ID is prefixed with -100:

    * ``user_id``
    * ``-chat_id``
    * ``-100channel_id``

    The original ID and the peer type class can be returned with
    a call to :meth:`resolve_id(marked_id)`.
    """
    # First we assert it's a Peer TLObject, or early return for integers
    if isinstance(peer, int):
        return peer if add_mark else resolve_id(peer)[0]

    # Tell the user to use their client to resolve InputPeerSelf if we got one
    if isinstance(peer, types.InputPeerSelf):
        _raise_cast_fail(peer, 'int (you might want to use client.get_peer_id)')

    try:
        peer = get_peer(peer)
    except TypeError:
        _raise_cast_fail(peer, 'int')

    if isinstance(peer, types.PeerUser):
        return peer.user_id
    elif isinstance(peer, types.PeerChat):
        # Check in case the user mixed things up to avoid blowing up
        if not (0 < peer.chat_id <= 0x7fffffff):
            peer.chat_id = resolve_id(peer.chat_id)[0]

        return -peer.chat_id if add_mark else peer.chat_id
    else:  # if isinstance(peer, types.PeerChannel):
        # Check in case the user mixed things up to avoid blowing up
        if not (0 < peer.channel_id <= 0x7fffffff):
            peer.channel_id = resolve_id(peer.channel_id)[0]

        if not add_mark:
            return peer.channel_id

        # Concat -100 through math tricks, .to_supergroup() on
        # Madeline IDs will be strictly positive -> log works.
        try:
            return -(peer.channel_id + pow(
                10, math.floor(math.log10(peer.channel_id) + 3)))
        except ValueError:
            raise TypeError('Cannot get marked ID of a channel '
                            'unless its ID is strictly positive') from None


def resolve_id(marked_id):
    """Given a marked ID, returns the original ID and its :tl:`Peer` type."""
    if marked_id >= 0:
        return marked_id, types.PeerUser

    # There have been report of chat IDs being 10000xyz, which means their
    # marked version is -10000xyz, which in turn looks like a channel but
    # it becomes 00xyz (= xyz). Hence, we must assert that there are only
    # two zeroes.
    m = re.match(r'-100([^0]\d*)', str(marked_id))
    if m:
        return int(m.group(1)), types.PeerChannel

    return -marked_id, types.PeerChat


def _rle_decode(data):
    """
    Decodes run-length-encoded `data`.
    """
    if not data:
        return data

    new = b''
    last = b''
    for cur in data:
        if last == b'\0':
            new += last * cur
            last = b''
        else:
            new += last
            last = bytes([cur])

    return new + last


def _rle_encode(string):
    new = b''
    count = 0
    for cur in string:
        if not cur:
            count += 1
        else:
            if count:
                new += b'\0' + bytes([count])
                count = 0

            new += bytes([cur])
    return new


def _decode_telegram_base64(string):
    """
    Decodes an url-safe base64-encoded string into its bytes
    by first adding the stripped necessary padding characters.

    This is the way Telegram shares binary data as strings,
    such as Bot API-style file IDs or invite links.

    Returns `None` if the input string was not valid.
    """
    try:
        return base64.urlsafe_b64decode(string + '=' * (len(string) % 4))
    except (binascii.Error, ValueError, TypeError):
        return None  # not valid base64, not valid ascii, not a string


def _encode_telegram_base64(string):
    """
    Inverse for `_decode_telegram_base64`.
    """
    try:
        return base64.urlsafe_b64encode(string).rstrip(b'=').decode('ascii')
    except (binascii.Error, ValueError, TypeError):
        return None  # not valid base64, not valid ascii, not a string


def resolve_bot_file_id(file_id):
    """
    Given a Bot API-style `file_id <telethon.tl.custom.file.File.id>`,
    returns the media it represents. If the `file_id <telethon.tl.custom.file.File.id>`
    is not valid, `None` is returned instead.

    Note that the `file_id <telethon.tl.custom.file.File.id>` does not have information
    such as image dimensions or file size, so these will be zero if present.

    For thumbnails, the photo ID and hash will always be zero.
    """
    data = _rle_decode(_decode_telegram_base64(file_id))
    if not data:
        return None

    # This isn't officially documented anywhere, but
    # we assume the last byte is some kind of "version".
    data, version = data[:-1], data[-1]
    if version not in (2, 4):
        return None

    if (version == 2 and len(data) == 24) or (version == 4 and len(data) == 25):
        if version == 2:
            file_type, dc_id, media_id, access_hash = struct.unpack('<iiqq', data)
        # elif version == 4:
        else:
            # TODO Figure out what the extra byte means
            file_type, dc_id, media_id, access_hash, _ = struct.unpack('<iiqqb', data)

        if not (1 <= dc_id <= 5):
            # Valid `file_id`'s must have valid DC IDs. Since this method is
            # called when sending a file and the user may have entered a path
            # they believe is correct but the file doesn't exist, this method
            # may detect a path as "valid" bot `file_id` even when it's not.
            # By checking the `dc_id`, we greatly reduce the chances of this
            # happening.
            return None

        attributes = []
        if file_type == 3 or file_type == 9:
            attributes.append(types.DocumentAttributeAudio(
                duration=0,
                voice=file_type == 3
            ))
        elif file_type == 4 or file_type == 13:
            attributes.append(types.DocumentAttributeVideo(
                duration=0,
                w=0,
                h=0,
                round_message=file_type == 13
            ))
        # elif file_type == 5:  # other, cannot know which
        elif file_type == 8:
            attributes.append(types.DocumentAttributeSticker(
                alt='',
                stickerset=types.InputStickerSetEmpty()
            ))
        elif file_type == 10:
            attributes.append(types.DocumentAttributeAnimated())

        return types.Document(
            id=media_id,
            access_hash=access_hash,
            date=None,
            mime_type='',
            size=0,
            thumbs=None,
            dc_id=dc_id,
            attributes=attributes,
            file_reference=b''
        )
    elif (version == 2 and len(data) == 44) or (version == 4 and len(data) == 49):
        if version == 2:
            (file_type, dc_id, media_id, access_hash,
                volume_id, secret, local_id) = struct.unpack('<iiqqqqi', data)
        # elif version == 4:
        else:
            # TODO Figure out what the extra five bytes mean
            (file_type, dc_id, media_id, access_hash,
                volume_id, secret, local_id, _) = struct.unpack('<iiqqqqi5s', data)

        if not (1 <= dc_id <= 5):
            return None

        # Thumbnails (small) always have ID 0; otherwise size 'x'
        photo_size = 's' if media_id or access_hash else 'x'
        return types.Photo(
            id=media_id,
            access_hash=access_hash,
            file_reference=b'',
            date=None,
            sizes=[types.PhotoSize(
                type=photo_size,
                location=types.FileLocationToBeDeprecated(
                    volume_id=volume_id,
                    local_id=local_id
                ),
                w=0,
                h=0,
                size=0
            )],
            dc_id=dc_id,
            has_stickers=None
        )


def pack_bot_file_id(file):
    """
    Inverse operation for `resolve_bot_file_id`.

    The only parameters this method will accept are :tl:`Document` and
    :tl:`Photo`, and it will return a variable-length ``file_id`` string.

    If an invalid parameter is given, it will ``return None``.
    """
    if isinstance(file, types.MessageMediaDocument):
        file = file.document
    elif isinstance(file, types.MessageMediaPhoto):
        file = file.photo

    if isinstance(file, types.Document):
        file_type = 5
        for attribute in file.attributes:
            if isinstance(attribute, types.DocumentAttributeAudio):
                file_type = 3 if attribute.voice else 9
            elif isinstance(attribute, types.DocumentAttributeVideo):
                file_type = 13 if attribute.round_message else 4
            elif isinstance(attribute, types.DocumentAttributeSticker):
                file_type = 8
            elif isinstance(attribute, types.DocumentAttributeAnimated):
                file_type = 10
            else:
                continue
            break

        return _encode_telegram_base64(_rle_encode(struct.pack(
            '<iiqqb', file_type, file.dc_id, file.id, file.access_hash, 2)))

    elif isinstance(file, types.Photo):
        size = next((x for x in reversed(file.sizes) if isinstance(
            x, (types.PhotoSize, types.PhotoCachedSize))), None)

        if not size:
            return None

        size = size.location
        return _encode_telegram_base64(_rle_encode(struct.pack(
            '<iiqqqqib', 2, file.dc_id, file.id, file.access_hash,
            size.volume_id, 0, size.local_id, 2  # 0 = old `secret`
        )))
    else:
        return None


def resolve_invite_link(link):
    """
    Resolves the given invite link. Returns a tuple of
    ``(link creator user id, global chat id, random int)``.

    Note that for broadcast channels, the link creator
    user ID will be zero to protect their identity.
    Normal chats and megagroup channels will have such ID.

    Note that the chat ID may not be accurate for chats
    with a link that were upgraded to megagroup, since
    the link can remain the same, but the chat ID will
    be correct once a new link is generated.
    """
    link_hash, is_link = parse_username(link)
    if not is_link:
        # Perhaps the user passed the link hash directly
        link_hash = link

    # Little known fact, but invite links with a
    # hex-string of bytes instead of base64 also works.
    if re.match(r'[a-fA-F\d]{32}', link_hash):
        payload = bytes.fromhex(link_hash)
    else:
        payload = _decode_telegram_base64(link_hash)

    try:
        return struct.unpack('>LLQ', payload)
    except (struct.error, TypeError):
        return None, None, None


def resolve_inline_message_id(inline_msg_id):
    """
    Resolves an inline message ID. Returns a tuple of
    ``(message id, peer, dc id, access hash)``

    The ``peer`` may either be a :tl:`PeerUser` referencing
    the user who sent the message via the bot in a private
    conversation or small group chat, or a :tl:`PeerChannel`
    if the message was sent in a channel.

    The ``access_hash`` does not have any use yet.
    """
    try:
        dc_id, message_id, pid, access_hash = \
            struct.unpack('<iiiq', _decode_telegram_base64(inline_msg_id))
        peer = types.PeerChannel(-pid) if pid < 0 else types.PeerUser(pid)
        return message_id, peer, dc_id, access_hash
    except (struct.error, TypeError):
        return None, None, None, None


def get_appropriated_part_size(file_size):
    """
    Gets the appropriated part size when uploading or downloading files,
    given an initial file size.
    """
    if file_size <= 104857600:  # 100MB
        return 128
    if file_size <= 786432000:  # 750MB
        return 256
    if file_size <= 1572864000:  # 1500MB
        return 512

    raise ValueError('File size too large')


def encode_waveform(waveform):
    """
    Encodes the input `bytes` into a 5-bit byte-string
    to be used as a voice note's waveform. See `decode_waveform`
    for the reverse operation.

    Example
        .. code-block:: python

            chat = ...
            file = 'my.ogg'

            # Send 'my.ogg' with a ascending-triangle waveform
            await client.send_file(chat, file, attributes=[types.DocumentAttributeAudio(
                duration=7,
                voice=True,
                waveform=utils.encode_waveform(bytes(range(2 ** 5))  # 2**5 because 5-bit
            )]

            # Send 'my.ogg' with a square waveform
            await client.send_file(chat, file, attributes=[types.DocumentAttributeAudio(
                duration=7,
                voice=True,
                waveform=utils.encode_waveform(bytes((31, 31, 15, 15, 15, 15, 31, 31)) * 4)
            )]
    """
    bits_count = len(waveform) * 5
    bytes_count = (bits_count + 7) // 8
    result = bytearray(bytes_count + 1)

    for i in range(len(waveform)):
        byte_index, bit_shift = divmod(i * 5, 8)
        value = (waveform[i] & 0b00011111) << bit_shift

        or_what = struct.unpack('<H', (result[byte_index:byte_index + 2]))[0]
        or_what |= value
        result[byte_index:byte_index + 2] = struct.pack('<H', or_what)

    return bytes(result[:bytes_count])


def decode_waveform(waveform):
    """
    Inverse operation of `encode_waveform`.
    """
    bit_count = len(waveform) * 8
    value_count = bit_count // 5
    if value_count == 0:
        return b''

    result = bytearray(value_count)
    for i in range(value_count - 1):
        byte_index, bit_shift = divmod(i * 5, 8)
        value = struct.unpack('<H', waveform[byte_index:byte_index + 2])[0]
        result[i] = (value >> bit_shift) & 0b00011111

    byte_index, bit_shift = divmod(value_count - 1, 8)
    if byte_index == len(waveform) - 1:
        value = waveform[byte_index]
    else:
        value = struct.unpack('<H', waveform[byte_index:byte_index + 2])[0]

    result[value_count - 1] = (value >> bit_shift) & 0b00011111
    return bytes(result)


class AsyncClassWrapper:
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, item):
        w = getattr(self.wrapped, item)
        async def wrapper(*args, **kwargs):
            val = w(*args, **kwargs)
            return await val if inspect.isawaitable(val) else val

        if callable(w):
            return wrapper
        else:
            return w


def stripped_photo_to_jpg(stripped):
    """
    Adds the JPG header and footer to a stripped image.

    Ported from https://github.com/telegramdesktop/tdesktop/blob/bec39d89e19670eb436dc794a8f20b657cb87c71/Telegram/SourceFiles/ui/image/image.cpp#L225
    """
    # NOTE: Changes here should update _stripped_real_length
    if len(stripped) < 3 or stripped[0] != 1:
        return stripped

    header = bytearray(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00(\x1c\x1e#\x1e\x19(#!#-+(0<dA<77<{X]Id\x91\x80\x99\x96\x8f\x80\x8c\x8a\xa0\xb4\xe6\xc3\xa0\xaa\xda\xad\x8a\x8c\xc8\xff\xcb\xda\xee\xf5\xff\xff\xff\x9b\xc1\xff\xff\xff\xfa\xff\xe6\xfd\xff\xf8\xff\xdb\x00C\x01+--<5<vAAv\xf8\xa5\x8c\xa5\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xff\xc0\x00\x11\x08\x00\x00\x00\x00\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0\x15br\xd1\n\x16$4\xe1%\xf1\x17\x18\x19\x1a&\'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00')
    footer = b"\xff\xd9"
    header[164] = stripped[1]
    header[166] = stripped[2]
    return bytes(header) + stripped[3:] + footer


def _stripped_real_length(stripped):
    if len(stripped) < 3 or stripped[0] != 1:
        return len(stripped)

    return len(stripped) + 622
