"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like an User, Chat, etc. into its Input version)
"""
import itertools
import math
import mimetypes
import os
import re
from collections import UserList
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

USERNAME_RE = re.compile(
    r'@|(?:https?://)?(?:www\.)?(?:telegram\.(?:me|dog)|t\.me)/(joinchat/)?'
)

# The only shorter-than-five-characters usernames are those used for some
# special, very well known bots. This list may be incomplete though:
#    "[...] @gif, @vid, @pic, @bing, @wiki, @imdb and @bold [...]"
#
# See https://telegram.org/blog/inline-bots#how-does-it-work
VALID_USERNAME_RE = re.compile(
    r'^([a-z]((?!__)[\w\d]){3,30}[a-z\d]'
    r'|gif|vid|pic|bing|wiki|imdb|bold|vote|like|coub|ya)$',
    re.IGNORECASE
)


class Default:
    """
    Sentinel value to indicate that the default value should be used.
    Currently used for the ``parse_mode``, where a ``None`` mode should
    be considered different from using the default.
    """


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
    Gets the display name for the given entity, if it's an :tl:`User`,
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
    if isinstance(media, (types.UserProfilePhoto,
                          types.ChatPhoto, types.MessageMediaPhoto)):
        return '.jpg'

    # Documents will come with a mime type
    if isinstance(media, types.MessageMediaDocument):
        media = media.document
    if isinstance(media, types.Document):
        if media.mime_type == 'application/octet-stream':
            # Octet stream are just bytes, which have no default extension
            return ''
        else:
            return guess_extension(media.mime_type) or ''

    return ''


def _raise_cast_fail(entity, target):
    raise TypeError('Cannot cast {} to any kind of {}.'.format(
        type(entity).__name__, target))


def get_input_peer(entity, allow_self=True):
    """
    Gets the input peer for the given "entity" (user, chat or channel).
    A ``TypeError`` is raised if the given entity isn't a supported type.
    """
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
        else:
            return types.InputPeerUser(entity.id, entity.access_hash or 0)

    if isinstance(entity, (types.Chat, types.ChatEmpty, types.ChatForbidden)):
        return types.InputPeerChat(entity.id)

    if isinstance(entity, (types.Channel, types.ChannelForbidden)):
        return types.InputPeerChannel(entity.id, entity.access_hash or 0)

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
    """Similar to :meth:`get_input_peer`, but for :tl:`InputChannel`'s alone."""
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
    """Similar to :meth:`get_input_peer`, but for :tl:`InputUser`'s alone."""
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
            id=document.id, access_hash=document.access_hash)

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

    if isinstance(photo, types.photos.Photo):
        photo = photo.photo

    if isinstance(photo, types.Photo):
        return types.InputPhoto(id=photo.id, access_hash=photo.access_hash)

    if isinstance(photo, types.PhotoEmpty):
        return types.InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


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


def get_input_media(media, is_photo=False):
    """
    Similar to :meth:`get_input_peer`, but for media.

    If the media is a file location and ``is_photo`` is known to be ``True``,
    it will be treated as an :tl:`InputMediaUploadedPhoto`.
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

    if isinstance(media, types.FileLocation):
        if is_photo:
            return types.InputMediaUploadedPhoto(file=media)
        else:
            return types.InputMediaUploadedDocument(
                file=media,
                mime_type='application/octet-stream',  # unknown, assume bytes
                attributes=[types.DocumentAttributeFilename('unnamed')]
            )

    if isinstance(media, types.MessageMediaGame):
        return types.InputMediaGame(id=media.game.id)

    if isinstance(media, (types.ChatPhoto, types.UserProfilePhoto)):
        if isinstance(media.photo_big, types.FileLocationUnavailable):
            media = media.photo_small
        else:
            media = media.photo_big
        return get_input_media(media, is_photo=True)

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
            types.FileLocationUnavailable)):
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


def get_message_id(message):
    """Sanitizes the 'reply_to' parameter a user may send"""
    if message is None:
        return None

    if isinstance(message, int):
        return message

    if hasattr(message, 'original_message'):
        return message.original_message.id

    try:
        if message.SUBCLASS_OF_ID == 0x790009e3:
            # hex(crc32(b'Message')) = 0x790009e3
            return message.id
    except AttributeError:
        pass

    raise TypeError('Invalid message type: {}'.format(type(message)))


def get_attributes(file, *, attributes=None, mime_type=None,
                   force_document=False, voice_note=False, video_note=False):
    """
    Get a list of attributes for the given file and
    the mime type as a tuple ([attribute], mime_type).
    """
    if isinstance(file, str):
        # Determine mime-type and attributes
        # Take the first element by using [0] since it returns a tuple
        if mime_type is None:
            mime_type = mimetypes.guess_type(file)[0]

        attr_dict = {types.DocumentAttributeFilename:
            types.DocumentAttributeFilename(os.path.basename(file))}

        if is_audio(file) and hachoir is not None:
            with hachoir.parser.createParser(file) as parser:
                m = hachoir.metadata.extractMetadata(parser)
                attr_dict[types.DocumentAttributeAudio] = \
                    types.DocumentAttributeAudio(
                        voice=voice_note,
                        title=m.get('title') if m.has('title') else None,
                        performer=m.get('author') if m.has('author') else None,
                        duration=int(m.get('duration').seconds
                                     if m.has('duration') else 0)
                    )

        if not force_document and is_video(file):
            if hachoir:
                with hachoir.parser.createParser(file) as parser:
                    m = hachoir.metadata.extractMetadata(parser)
                    doc = types.DocumentAttributeVideo(
                        round_message=video_note,
                        w=m.get('width') if m.has('width') else 0,
                        h=m.get('height') if m.has('height') else 0,
                        duration=int(m.get('duration').seconds
                                     if m.has('duration') else 0)
                    )
            else:
                doc = types.DocumentAttributeVideo(
                    0, 1, 1, round_message=video_note)

            attr_dict[types.DocumentAttributeVideo] = doc
    else:
        attr_dict = {types.DocumentAttributeFilename:
            types.DocumentAttributeFilename(
                os.path.basename(getattr(file, 'name', None) or 'unnamed'))}

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
            location.id, location.access_hash, location.version))
    elif isinstance(location, types.Photo):
        try:
            location = next(
                x for x in reversed(location.sizes)
                if not isinstance(x, types.PhotoSizeEmpty)
            ).location
        except StopIteration:
            pass

    if isinstance(location, (
            types.FileLocation, types.FileLocationUnavailable)):
        return (getattr(location, 'dc_id', None), types.InputFileLocation(
            location.volume_id, location.local_id, location.secret))

    _raise_cast_fail(location, 'InputFileLocation')


def _get_extension(file):
    """
    Gets the extension for the given file, which can be either a
    str or an ``open()``'ed file (which has a ``.name`` attribute).
    """
    if isinstance(file, str):
        return os.path.splitext(file)[-1]
    elif getattr(file, 'name', None):
        return _get_extension(file.name)
    else:
        return ''


def is_image(file):
    """
    Returns ``True`` if the file extension looks like an image file to Telegram.
    """
    return re.match(r'\.(png|jpe?g)', _get_extension(file), re.IGNORECASE)


def is_gif(file):
    """
    Returns ``True`` if the file extension looks like a gif file to Telegram.
    """
    return re.match(r'\.gif', _get_extension(file), re.IGNORECASE)


def is_audio(file):
    """Returns ``True`` if the file extension looks like an audio file."""
    file = 'a' + _get_extension(file)
    return (mimetypes.guess_type(file)[0] or '').startswith('audio/')


def is_video(file):
    """Returns ``True`` if the file extension looks like a video file."""
    file = 'a' + _get_extension(file)
    return (mimetypes.guess_type(file)[0] or '').startswith('video/')


def is_list_like(obj):
    """
    Returns ``True`` if the given object looks like a list.

    Checking ``if hasattr(obj, '__iter__')`` and ignoring ``str/bytes`` is not
    enough. Things like ``open()`` are also iterable (and probably many
    other things), so just support the commonly known list-like objects.
    """
    return isinstance(obj, (list, tuple, set, dict,
                            UserList, GeneratorType))


def parse_phone(phone):
    """Parses the given phone, or returns ``None`` if it's invalid."""
    if isinstance(phone, int):
        return str(phone)
    else:
        phone = re.sub(r'[+()\s-]', '', str(phone))
        if phone.isdigit():
            return phone


def parse_username(username):
    """Parses the given username or channel access hash, given
       a string, username or URL. Returns a tuple consisting of
       both the stripped, lowercase username and whether it is
       a joinchat/ hash (in which case is not lowercase'd).

       Returns ``None`` if the ``username`` is not valid.
    """
    username = username.strip()
    m = USERNAME_RE.match(username)
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


def get_peer_id(peer, add_mark=True):
    """
    Finds the ID of the given peer, and converts it to the "bot api" format
    so it the peer can be identified back. User ID is left unmodified,
    chat ID is negated, and channel ID is prefixed with -100.

    The original ID and the peer type class can be returned with
    a call to :meth:`resolve_id(marked_id)`.
    """
    # First we assert it's a Peer TLObject, or early return for integers
    if isinstance(peer, int):
        return peer if add_mark else resolve_id(peer)[0]

    try:
        if peer.SUBCLASS_OF_ID not in (0x2d45687, 0xc91c90b6):
            if isinstance(peer, (
                    types.contacts.ResolvedPeer, types.InputNotifyPeer,
                    types.TopPeer)):
                peer = peer.peer
            else:
                # Not a Peer or an InputPeer, so first get its Input version
                peer = get_input_peer(peer, allow_self=False)
    except AttributeError:
        _raise_cast_fail(peer, 'int')

    # Set the right ID/kind, or raise if the TLObject is not recognised
    if isinstance(peer, (types.PeerUser, types.InputPeerUser)):
        return peer.user_id
    elif isinstance(peer, (types.PeerChat, types.InputPeerChat)):
        # Check in case the user mixed things up to avoid blowing up
        if not (0 < peer.chat_id <= 0x7fffffff):
            peer.chat_id = resolve_id(peer.chat_id)[0]

        return -peer.chat_id if add_mark else peer.chat_id
    elif isinstance(peer, (
            types.PeerChannel, types.InputPeerChannel, types.ChannelFull)):
        if isinstance(peer, types.ChannelFull):
            # Special case: .get_input_peer can't return InputChannel from
            # ChannelFull since it doesn't have an .access_hash attribute.
            i = peer.id
        else:
            i = peer.channel_id

        # Check in case the user mixed things up to avoid blowing up
        if not (0 < i <= 0x7fffffff):
            i = resolve_id(i)[0]
            if isinstance(peer, types.ChannelFull):
                peer.id = i
            else:
                peer.channel_id = i

        if add_mark:
            # Concat -100 through math tricks, .to_supergroup() on
            # Madeline IDs will be strictly positive -> log works.
            return -(i + pow(10, math.floor(math.log10(i) + 3)))
        else:
            return i

    _raise_cast_fail(peer, 'int')


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
