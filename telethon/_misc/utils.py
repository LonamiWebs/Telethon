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
import pathlib
import re
import struct
from collections import namedtuple
from mimetypes import guess_extension
from types import GeneratorType

from .helpers import add_surrogate, del_surrogate, strip_text
from . import markdown, html
from .. import _tl

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

mimetypes.add_type('application/x-tgsticker', '.tgs')

USERNAME_RE = re.compile(
    r'@|(?:https?://)?(?:www\.)?(?:telegram\.(?:me|dog)|t\.me)/(@|\+|joinchat/)?'
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
    r'^([a-z](?:(?!__)\w){3,30}[a-z\d]'
    r'|gif|vid|pic|bing|wiki|imdb|bold|vote|like|coub)$',
    re.IGNORECASE
)

_FileInfo = namedtuple('FileInfo', 'dc_id location size')

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
    if isinstance(entity, _tl.User):
        if entity.last_name and entity.first_name:
            return '{} {}'.format(entity.first_name, entity.last_name)
        elif entity.first_name:
            return entity.first_name
        elif entity.last_name:
            return entity.last_name
        else:
            return ''

    elif isinstance(entity, (_tl.Chat, _tl.ChatForbidden, _tl.Channel)):
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
        if isinstance(media, (_tl.UserProfilePhoto, _tl.ChatPhoto)):
            return '.jpg'

    # Documents will come with a mime type
    if isinstance(media, _tl.MessageMediaDocument):
        media = media.document
    if isinstance(media, (
            _tl.Document, _tl.WebDocument, _tl.WebDocumentNoProxy)):
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

    if isinstance(entity, _tl.User):
        if entity.is_self and allow_self:
            return _tl.InputPeerSelf()
        elif (entity.access_hash is not None and not entity.min) or not check_hash:
            return _tl.InputPeerUser(entity.id, entity.access_hash)
        else:
            raise TypeError('User without access_hash or min info cannot be input')

    if isinstance(entity, (_tl.Chat, _tl.ChatEmpty, _tl.ChatForbidden)):
        return _tl.InputPeerChat(entity.id)

    if isinstance(entity, _tl.Channel):
        if (entity.access_hash is not None and not entity.min) or not check_hash:
            return _tl.InputPeerChannel(entity.id, entity.access_hash)
        else:
            raise TypeError('Channel without access_hash or min info cannot be input')
    if isinstance(entity, _tl.ChannelForbidden):
        # "channelForbidden are never min", and since their hash is
        # also not optional, we assume that this truly is the case.
        return _tl.InputPeerChannel(entity.id, entity.access_hash)

    if isinstance(entity, _tl.InputUser):
        return _tl.InputPeerUser(entity.user_id, entity.access_hash)

    if isinstance(entity, _tl.InputChannel):
        return _tl.InputPeerChannel(entity.channel_id, entity.access_hash)

    if isinstance(entity, _tl.InputUserSelf):
        return _tl.InputPeerSelf()

    if isinstance(entity, _tl.InputUserFromMessage):
        return _tl.InputPeerUserFromMessage(entity.peer, entity.msg_id, entity.user_id)

    if isinstance(entity, _tl.InputChannelFromMessage):
        return _tl.InputPeerChannelFromMessage(entity.peer, entity.msg_id, entity.channel_id)

    if isinstance(entity, _tl.UserEmpty):
        return _tl.InputPeerEmpty()

    if isinstance(entity, _tl.UserFull):
        return get_input_peer(entity.user)

    if isinstance(entity, _tl.ChatFull):
        return _tl.InputPeerChat(entity.id)

    if isinstance(entity, _tl.PeerChat):
        return _tl.InputPeerChat(entity.chat_id)

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

    if isinstance(entity, (_tl.Channel, _tl.ChannelForbidden)):
        return _tl.InputChannel(entity.id, entity.access_hash or 0)

    if isinstance(entity, _tl.InputPeerChannel):
        return _tl.InputChannel(entity.channel_id, entity.access_hash)

    if isinstance(entity, _tl.InputPeerChannelFromMessage):
        return _tl.InputChannelFromMessage(entity.peer, entity.msg_id, entity.channel_id)

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

    if isinstance(entity, _tl.User):
        if entity.is_self:
            return _tl.InputUserSelf()
        else:
            return _tl.InputUser(entity.id, entity.access_hash or 0)

    if isinstance(entity, _tl.InputPeerSelf):
        return _tl.InputUserSelf()

    if isinstance(entity, (_tl.UserEmpty, _tl.InputPeerEmpty)):
        return _tl.InputUserEmpty()

    if isinstance(entity, _tl.UserFull):
        return get_input_user(entity.user)

    if isinstance(entity, _tl.InputPeerUser):
        return _tl.InputUser(entity.user_id, entity.access_hash)

    if isinstance(entity, _tl.InputPeerUserFromMessage):
        return _tl.InputUserFromMessage(entity.peer, entity.msg_id, entity.user_id)

    _raise_cast_fail(entity, 'InputUser')


def get_input_dialog(dialog):
    """Similar to :meth:`get_input_peer`, but for dialogs"""
    try:
        if dialog.SUBCLASS_OF_ID == 0xa21c9795:  # crc32(b'InputDialogPeer')
            return dialog
        if dialog.SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
            return _tl.InputDialogPeer(dialog)
    except AttributeError:
        _raise_cast_fail(dialog, 'InputDialogPeer')

    try:
        return _tl.InputDialogPeer(get_input_peer(dialog))
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

    if isinstance(document, _tl.Document):
        return _tl.InputDocument(
            id=document.id, access_hash=document.access_hash,
            file_reference=document.file_reference)

    if isinstance(document, _tl.DocumentEmpty):
        return _tl.InputDocumentEmpty()

    if isinstance(document, _tl.MessageMediaDocument):
        return get_input_document(document.document)

    if isinstance(document, _tl.Message):
        return get_input_document(document.media)

    _raise_cast_fail(document, 'InputDocument')


def get_input_photo(photo):
    """Similar to :meth:`get_input_peer`, but for photos"""
    try:
        if photo.SUBCLASS_OF_ID == 0x846363e0:  # crc32(b'InputPhoto'):
            return photo
    except AttributeError:
        _raise_cast_fail(photo, 'InputPhoto')

    if isinstance(photo, _tl.Message):
        photo = photo.media

    if isinstance(photo, (_tl.photos.Photo, _tl.MessageMediaPhoto)):
        photo = photo.photo

    if isinstance(photo, _tl.Photo):
        return _tl.InputPhoto(id=photo.id, access_hash=photo.access_hash,
                                file_reference=photo.file_reference)

    if isinstance(photo, _tl.PhotoEmpty):
        return _tl.InputPhotoEmpty()

    if isinstance(photo, _tl.messages.ChatFull):
        photo = photo.full_chat

    if isinstance(photo, _tl.ChannelFull):
        return get_input_photo(photo.chat_photo)
    elif isinstance(photo, _tl.UserFull):
        return get_input_photo(photo.profile_photo)
    elif isinstance(photo, (_tl.Channel, _tl.Chat, _tl.User)):
        return get_input_photo(photo.photo)

    if isinstance(photo, (_tl.UserEmpty, _tl.ChatEmpty,
                          _tl.ChatForbidden, _tl.ChannelForbidden)):
        return _tl.InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


def get_input_chat_photo(photo):
    """Similar to :meth:`get_input_peer`, but for chat photos"""
    try:
        if photo.SUBCLASS_OF_ID == 0xd4eb2d74:  # crc32(b'InputChatPhoto')
            return photo
        elif photo.SUBCLASS_OF_ID == 0xe7655f1f:  # crc32(b'InputFile'):
            return _tl.InputChatUploadedPhoto(photo)
    except AttributeError:
        _raise_cast_fail(photo, 'InputChatPhoto')

    photo = get_input_photo(photo)
    if isinstance(photo, _tl.InputPhoto):
        return _tl.InputChatPhoto(photo)
    elif isinstance(photo, _tl.InputPhotoEmpty):
        return _tl.InputChatPhotoEmpty()

    _raise_cast_fail(photo, 'InputChatPhoto')


def get_input_geo(geo):
    """Similar to :meth:`get_input_peer`, but for geo points"""
    try:
        if geo.SUBCLASS_OF_ID == 0x430d225:  # crc32(b'InputGeoPoint'):
            return geo
    except AttributeError:
        _raise_cast_fail(geo, 'InputGeoPoint')

    if isinstance(geo, _tl.GeoPoint):
        return _tl.InputGeoPoint(lat=geo.lat, long=geo.long)

    if isinstance(geo, _tl.GeoPointEmpty):
        return _tl.InputGeoPointEmpty()

    if isinstance(geo, _tl.MessageMediaGeo):
        return get_input_geo(geo.geo)

    if isinstance(geo, _tl.Message):
        return get_input_geo(geo.media)

    _raise_cast_fail(geo, 'InputGeoPoint')


def get_input_media(
        media, *,
        is_photo=False, attributes=None, force_document=False,
        voice_note=False, video_note=False, supports_streaming=False,
        ttl=None
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
            return _tl.InputMediaPhoto(media, ttl_seconds=ttl)
        elif media.SUBCLASS_OF_ID == 0xf33fdb68:  # crc32(b'InputDocument')
            return _tl.InputMediaDocument(media, ttl_seconds=ttl)
    except AttributeError:
        _raise_cast_fail(media, 'InputMedia')

    if isinstance(media, _tl.MessageMediaPhoto):
        return _tl.InputMediaPhoto(
            id=get_input_photo(media.photo),
            ttl_seconds=ttl or media.ttl_seconds
        )

    if isinstance(media, (_tl.Photo, _tl.photos.Photo, _tl.PhotoEmpty)):
        return _tl.InputMediaPhoto(
            id=get_input_photo(media),
            ttl_seconds=ttl
        )

    if isinstance(media, _tl.MessageMediaDocument):
        return _tl.InputMediaDocument(
            id=get_input_document(media.document),
            ttl_seconds=ttl or media.ttl_seconds
        )

    if isinstance(media, (_tl.Document, _tl.DocumentEmpty)):
        return _tl.InputMediaDocument(
            id=get_input_document(media),
            ttl_seconds=ttl
        )

    if isinstance(media, (_tl.InputFile, _tl.InputFileBig)):
        if is_photo:
            return _tl.InputMediaUploadedPhoto(file=media, ttl_seconds=ttl)
        else:
            attrs, mime = get_attributes(
                media,
                attributes=attributes,
                force_document=force_document,
                voice_note=voice_note,
                video_note=video_note,
                supports_streaming=supports_streaming
            )
            return _tl.InputMediaUploadedDocument(
                file=media, mime_type=mime, attributes=attrs, force_file=force_document,
                ttl_seconds=ttl)

    if isinstance(media, _tl.MessageMediaGame):
        return _tl.InputMediaGame(id=_tl.InputGameID(
            id=media.game.id,
            access_hash=media.game.access_hash
        ))

    if isinstance(media, _tl.MessageMediaContact):
        return _tl.InputMediaContact(
            phone_number=media.phone_number,
            first_name=media.first_name,
            last_name=media.last_name,
            vcard=''
        )

    if isinstance(media, _tl.MessageMediaGeo):
        return _tl.InputMediaGeoPoint(geo_point=get_input_geo(media.geo))

    if isinstance(media, _tl.MessageMediaVenue):
        return _tl.InputMediaVenue(
            geo_point=get_input_geo(media.geo),
            title=media.title,
            address=media.address,
            provider=media.provider,
            venue_id=media.venue_id,
            venue_type=''
        )

    if isinstance(media, _tl.MessageMediaDice):
        return _tl.InputMediaDice(media.emoticon)

    if isinstance(media, (
            _tl.MessageMediaEmpty, _tl.MessageMediaUnsupported,
            _tl.ChatPhotoEmpty, _tl.UserProfilePhotoEmpty,
            _tl.ChatPhoto, _tl.UserProfilePhoto)):
        return _tl.InputMediaEmpty()

    if isinstance(media, _tl.Message):
        return get_input_media(media.media, is_photo=is_photo, ttl=ttl)

    if isinstance(media, _tl.MessageMediaPoll):
        if media.poll.quiz:
            if not media.results.results:
                # A quiz has correct answers, which we don't know until answered.
                # If the quiz hasn't been answered we can't reconstruct it properly.
                raise TypeError('Cannot cast unanswered quiz to any kind of InputMedia.')

            correct_answers = [r.option for r in media.results.results if r.correct]
        else:
            correct_answers = None

        return _tl.InputMediaPoll(
            poll=media.poll,
            correct_answers=correct_answers,
            solution=media.results.solution,
            solution_entities=media.results.solution_entities,
        )

    if isinstance(media, _tl.Poll):
        return _tl.InputMediaPoll(media)

    _raise_cast_fail(media, 'InputMedia')


def get_input_message(message):
    """Similar to :meth:`get_input_peer`, but for input messages."""
    try:
        if isinstance(message, int):  # This case is really common too
            return _tl.InputMessageID(message)
        elif message.SUBCLASS_OF_ID == 0x54b6bcc5:  # crc32(b'InputMessage'):
            return message
        elif message.SUBCLASS_OF_ID == 0x790009e3:  # crc32(b'Message'):
            return _tl.InputMessageID(message.id)
    except AttributeError:
        pass

    _raise_cast_fail(message, 'InputMedia')


def get_input_group_call(call):
    """Similar to :meth:`get_input_peer`, but for input calls."""
    try:
        if call.SUBCLASS_OF_ID == 0x58611ab1:  # crc32(b'InputGroupCall')
            return call
        elif call.SUBCLASS_OF_ID == 0x20b4f320:  # crc32(b'GroupCall')
            return _tl.InputGroupCall(id=call.id, access_hash=call.access_hash)
    except AttributeError:
        _raise_cast_fail(call, 'InputGroupCall')


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
    if not hachoir:
        return

    stream = None
    close_stream = True
    seekable = True

    # The parser may fail and we don't want to crash if
    # the extraction process fails.
    try:
        # Note: aiofiles are intentionally left out for simplicity.
        # `helpers._FileStream` is async only for simplicity too, so can't
        # reuse it here.
        if isinstance(file, str):
            stream = open(file, 'rb')
        elif isinstance(file, bytes):
            stream = io.BytesIO(file)
        else:
            stream = file
            close_stream = False
            if getattr(file, 'seekable', None):
                seekable = file.seekable()
            else:
                seekable = False

        if not seekable:
            return None

        pos = stream.tell()
        filename = getattr(file, 'name', '')

        parser = hachoir.parser.guess.guessParser(hachoir.stream.InputIOStream(
            stream,
            source='file:' + filename,
            tags=[],
            filename=filename
        ))

        return hachoir.metadata.extractMetadata(parser)

    except Exception as e:
        _log.warning('Failed to analyze %s: %s %s', file, e.__class__, e)

    finally:
        if stream and close_stream:
            stream.close()
        elif stream and seekable:
            stream.seek(pos)


def get_attributes(file, *, attributes=None, mime_type=None,
                   force_document=False, voice_note=False, video_note=False,
                   supports_streaming=False, thumb=None):
    """
    Get a list of attributes for the given file and
    the mime type as a tuple ([attribute], mime_type).
    """
    # Note: ``file.name`` works for :tl:`InputFile` and some `IOBase` streams
    name = file if isinstance(file, str) else getattr(file, 'name', 'unnamed')
    if mime_type is None:
        mime_type = mimetypes.guess_type(name)[0]

    attr_dict = {_tl.DocumentAttributeFilename:
        _tl.DocumentAttributeFilename(os.path.basename(name))}

    if is_audio(file):
        m = _get_metadata(file)
        if m:
            if m.has('author'):
                performer = m.get('author')
            elif m.has('artist'):
                performer = m.get('artist')
            else:
                performer = None

            attr_dict[_tl.DocumentAttributeAudio] = \
                _tl.DocumentAttributeAudio(
                    voice=voice_note,
                    title=m.get('title') if m.has('title') else None,
                    performer=performer,
                    duration=int(m.get('duration').seconds
                                 if m.has('duration') else 0)
                )

    if not force_document and is_video(file):
        m = _get_metadata(file)
        if m:
            doc = _tl.DocumentAttributeVideo(
                round_message=video_note,
                w=m.get('width') if m.has('width') else 1,
                h=m.get('height') if m.has('height') else 1,
                duration=int(m.get('duration').seconds
                             if m.has('duration') else 1),
                supports_streaming=supports_streaming
            )
        elif thumb:
            t_m = _get_metadata(thumb)
            width = 1
            height = 1
            if t_m and t_m.has("width"):
                width = t_m.get("width")
            if t_m and t_m.has("height"):
                height = t_m.get("height")

            doc = _tl.DocumentAttributeVideo(
                0, width, height, round_message=video_note,
                supports_streaming=supports_streaming)
        else:
            doc = _tl.DocumentAttributeVideo(
                0, 1, 1, round_message=video_note,
                supports_streaming=supports_streaming)

        attr_dict[_tl.DocumentAttributeVideo] = doc

    if voice_note:
        if _tl.DocumentAttributeAudio in attr_dict:
            attr_dict[_tl.DocumentAttributeAudio].voice = True
        else:
            attr_dict[_tl.DocumentAttributeAudio] = \
                _tl.DocumentAttributeAudio(0, voice=True)

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


def sanitize_parse_mode(mode, *, _nop_parse=lambda t: (t, []), _nop_unparse=lambda t, e: t):
    if mode is None:
        mode = (_nop_parse, _nop_unparse)
    elif isinstance(mode, str):
        mode = mode.lower()
        if mode in ('md', 'markdown'):
            mode = (markdown.parse, markdown.unparse)
        elif mode in ('htm', 'html'):
            mode = (html.parse, html.unparse)
        else:
            raise ValueError(f'mode must be one of md, markdown, htm or html, but was {mode!r}')
    elif callable(mode):
        mode = (mode, _nop_unparse)
    elif isinstance(mode, tuple):
        if not (len(mode) == 2 and callable(mode[0]) and callable(mode[1])):
            raise ValueError(f'mode must be a tuple of exactly two callables')
    else:
        raise TypeError(f'mode must be either a str, callable or tuple, but was {mode!r}')

    return mode


def get_input_location(location):
    """
    Similar to :meth:`get_input_peer`, but for input messages.

    Note that this returns a tuple ``(dc_id, location)``, the
    ``dc_id`` being present if known.
    """
    info = _get_file_info(location)
    return info.dc_id, info.location


def _get_file_info(location):
    try:
        if location.SUBCLASS_OF_ID == 0x1523d462:
            return _FileInfo(None, location, None)  # crc32(b'InputFileLocation'):
    except AttributeError:
        _raise_cast_fail(location, 'InputFileLocation')

    if isinstance(location, _tl.Message):
        location = location.media

    if isinstance(location, _tl.MessageMediaDocument):
        location = location.document
    elif isinstance(location, _tl.MessageMediaPhoto):
        location = location.photo

    if isinstance(location, _tl.Document):
        return _FileInfo(location.dc_id, _tl.InputDocumentFileLocation(
            id=location.id,
            access_hash=location.access_hash,
            file_reference=location.file_reference,
            thumb_size=''  # Presumably to download one of its thumbnails
        ), location.size)
    elif isinstance(location, _tl.Photo):
        return _FileInfo(location.dc_id, _tl.InputPhotoFileLocation(
            id=location.id,
            access_hash=location.access_hash,
            file_reference=location.file_reference,
            thumb_size=location.sizes[-1].type
        ), _photo_size_byte_count(location.sizes[-1]))

    _raise_cast_fail(location, 'InputFileLocation')


def _get_extension(file):
    """
    Gets the extension for the given file, which can be either a
    str or an ``open()``'ed file (which has a ``.name`` attribute).
    """
    if isinstance(file, str):
        return os.path.splitext(file)[-1]
    elif isinstance(file, pathlib.Path):
        return file.suffix
    elif isinstance(file, bytes):
        kind = imghdr.what(io.BytesIO(file))
        return ('.' + kind) if kind else ''
    elif isinstance(file, io.IOBase) and not isinstance(file, io.TextIOBase) and file.seekable():
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
    return bool(re.match(r'\.(png|jpe?g)', _get_extension(file), re.IGNORECASE))


def is_gif(file):
    """
    Returns `True` if the file extension looks like a gif file to Telegram.
    """
    return re.match(r'\.gif', _get_extension(file), re.IGNORECASE)


def is_audio(file):
    """Returns `True` if the file has an audio mime type."""
    ext = _get_extension(file)
    if not ext:
        metadata = _get_metadata(file)
        if metadata and metadata.has('mime_type'):
            return metadata.get('mime_type').startswith('audio/')
        else:
            return False
    else:
        file = 'a' + ext
        return (mimetypes.guess_type(file)[0] or '').startswith('audio/')


def is_video(file):
    """Returns `True` if the file has a video mime type."""
    ext = _get_extension(file)
    if not ext:
        metadata = _get_metadata(file)
        if metadata and metadata.has('mime_type'):
            return metadata.get('mime_type').startswith('video/')
        else:
            return False
    else:
        file = 'a' + ext
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
        if peer.SUBCLASS_OF_ID == 0x2d45687:
            return peer
        elif isinstance(peer, (
                _tl.contacts.ResolvedPeer, _tl.InputNotifyPeer,
                _tl.TopPeer, _tl.Dialog, _tl.DialogPeer)):
            return peer.peer
        elif isinstance(peer, _tl.ChannelFull):
            return _tl.PeerChannel(peer.id)
        elif isinstance(peer, _tl.UserEmpty):
            return _tl.PeerUser(peer.id)
        elif isinstance(peer, _tl.ChatEmpty):
            return _tl.PeerChat(peer.id)

        if peer.SUBCLASS_OF_ID in (0x7d7c6f86, 0xd9c7fc18):
            # ChatParticipant, ChannelParticipant
            return _tl.PeerUser(peer.user_id)

        peer = get_input_peer(peer, allow_self=False, check_hash=False)
        if isinstance(peer, (_tl.InputPeerUser, _tl.InputPeerUserFromMessage)):
            return _tl.PeerUser(peer.user_id)
        elif isinstance(peer, _tl.InputPeerChat):
            return _tl.PeerChat(peer.chat_id)
        elif isinstance(peer, (_tl.InputPeerChannel, _tl.InputPeerChannelFromMessage)):
            return _tl.PeerChannel(peer.channel_id)
    except (AttributeError, TypeError):
        pass
    _raise_cast_fail(peer, 'Peer')


def get_peer_id(peer):
    """
    Extract the integer ID from the given :tl:`Peer`.
    """
    pid = getattr(peer, 'user_id', None) or getattr(peer, 'channel_id', None) or getattr(peer, 'chat_id', None)
    if not isinstance(pid, int):
        _raise_cast_fail(peer, 'int')

    return pid


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
    Decodes a url-safe base64-encoded string into its bytes
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
        peer = _tl.PeerChannel(-pid) if pid < 0 else _tl.PeerUser(pid)
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
    if file_size <= 2097152000:  # 2000MB
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
            await client.send_file(chat, file, attributes=[_tl.DocumentAttributeAudio(
                duration=7,
                voice=True,
                waveform=utils.encode_waveform(bytes(range(2 ** 5))  # 2**5 because 5-bit
            )]

            # Send 'my.ogg' with a square waveform
            await client.send_file(chat, file, attributes=[_tl.DocumentAttributeAudio(
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


def split_text(text, entities, *, limit=4096, max_entities=100, split_at=(r'\n', r'\s', '.')):
    """
    Split a message text and entities into multiple messages, each with their
    own set of entities. This allows sending a very large message as multiple
    messages while respecting the formatting.

    Arguments
        text (`str`):
            The message text.

        entities (List[:tl:`MessageEntity`])
            The formatting entities.

        limit (`int`):
            The maximum message length of each individual message.

        max_entities (`int`):
            The maximum amount of entities that will be present in each
            individual message.

        split_at (Tuplel[`str`]):
            The list of regular expressions that will determine where to split
            the text. By default, a newline is searched. If no newline is
            present, a space is searched. If no space is found, the split will
            be made at any character.

            The last expression should always match a character, or else the
            text will stop being splitted and the resulting text may be larger
            than the limit.

    Yields
        Pairs of ``(str, entities)`` with the split message.

    Example
        .. code-block:: python

            from telethon import utils
            from telethon.extensions import markdown

            very_long_markdown_text = "..."
            text, entities = markdown.parse(very_long_markdown_text)

            for text, entities in utils.split_text(text, entities):
                await client.send_message(chat, text, formatting_entities=entities)
    """
    # TODO add test cases (multiple entities beyond cutoff, at cutoff, splitting at emoji)
    # TODO try to optimize this a bit more? (avoid new_ent, smarter update method)
    def update(ent, **updates):
        kwargs = ent.to_dict()
        del kwargs['_']
        kwargs.update(updates)
        return ent.__class__(**kwargs)

    text = add_surrogate(text)
    split_at = tuple(map(re.compile, split_at))

    while True:
        if len(entities) > max_entities:
            last_ent = entities[max_entities - 1]
            cur_limit = min(limit, last_ent.offset + last_ent.length)
        else:
            cur_limit = limit

        if len(text) <= cur_limit:
            break

        for split in split_at:
            for i in reversed(range(cur_limit)):
                m = split.match(text, pos=i)
                if m:
                    cur_text, new_text = text[:m.end()], text[m.end():]
                    cur_ent, new_ent = [], []
                    for ent in entities:
                        if ent.offset < m.end():
                            if ent.offset + ent.length > m.end():
                                cur_ent.append(update(ent, length=m.end() - ent.offset))
                                new_ent.append(update(ent, offset=0, length=ent.offset + ent.length - m.end()))
                            else:
                                cur_ent.append(ent)
                        else:
                            new_ent.append(update(ent, offset=ent.offset - m.end()))

                    yield del_surrogate(cur_text), cur_ent
                    text, entities = new_text, new_ent
                    break
            else:
                continue
            break
        else:
            # Can't find where to split, just return the remaining text and entities
            break

    yield del_surrogate(text), entities


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
    # NOTE: Changes here should update _photo_size_byte_count
    if len(stripped) < 3 or stripped[0] != 1:
        return stripped

    header = bytearray(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00(\x1c\x1e#\x1e\x19(#!#-+(0<dA<77<{X]Id\x91\x80\x99\x96\x8f\x80\x8c\x8a\xa0\xb4\xe6\xc3\xa0\xaa\xda\xad\x8a\x8c\xc8\xff\xcb\xda\xee\xf5\xff\xff\xff\x9b\xc1\xff\xff\xff\xfa\xff\xe6\xfd\xff\xf8\xff\xdb\x00C\x01+--<5<vAAv\xf8\xa5\x8c\xa5\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xf8\xff\xc0\x00\x11\x08\x00\x00\x00\x00\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0\x15br\xd1\n\x16$4\xe1%\xf1\x17\x18\x19\x1a&\'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00')
    footer = b"\xff\xd9"
    header[164] = stripped[1]
    header[166] = stripped[2]
    return bytes(header) + stripped[3:] + footer


def _photo_size_byte_count(size):
    if isinstance(size, _tl.PhotoSize):
        return size.size
    elif isinstance(size, _tl.PhotoStrippedSize):
        if len(size.bytes) < 3 or size.bytes[0] != 1:
            return len(size.bytes)

        return len(size.bytes) + 622
    elif isinstance(size, _tl.PhotoCachedSize):
        return len(size.bytes)
    elif isinstance(size, _tl.PhotoSizeEmpty):
        return 0
    elif isinstance(size, _tl.PhotoSizeProgressive):
        return max(size.sizes)
    else:
        return None
