"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like an User, Chat, etc. into its Input version)
"""
import math
import mimetypes
import re
import types
from collections import UserList
from mimetypes import add_type, guess_extension

from .tl.types import (
    Channel, ChannelForbidden, Chat, ChatEmpty, ChatForbidden, ChatFull,
    ChatPhoto, InputPeerChannel, InputPeerChat, InputPeerUser, InputPeerEmpty,
    MessageMediaDocument, MessageMediaPhoto, PeerChannel, InputChannel,
    UserEmpty, InputUser, InputUserEmpty, InputUserSelf, InputPeerSelf,
    PeerChat, PeerUser, User, UserFull, UserProfilePhoto, Document,
    MessageMediaContact, MessageMediaEmpty, MessageMediaGame, MessageMediaGeo,
    MessageMediaUnsupported, MessageMediaVenue, InputMediaContact,
    InputMediaDocument, InputMediaEmpty, InputMediaGame,
    InputMediaGeoPoint, InputMediaPhoto, InputMediaVenue, InputDocument,
    DocumentEmpty, InputDocumentEmpty, Message, GeoPoint, InputGeoPoint,
    GeoPointEmpty, InputGeoPointEmpty, Photo, InputPhoto, PhotoEmpty,
    InputPhotoEmpty, FileLocation, ChatPhotoEmpty, UserProfilePhotoEmpty,
    FileLocationUnavailable, InputMediaUploadedDocument, ChannelFull,
    InputMediaUploadedPhoto, DocumentAttributeFilename, photos,
    TopPeer, InputNotifyPeer
)
from .tl.types.contacts import ResolvedPeer

USERNAME_RE = re.compile(
    r'@|(?:https?://)?(?:www\.)?(?:telegram\.(?:me|dog)|t\.me)/(joinchat/)?'
)

VALID_USERNAME_RE = re.compile(r'^[a-zA-Z][\w\d]{3,30}[a-zA-Z\d]$')


def get_display_name(entity):
    """
    Gets the display name for the given entity, if it's an ``User``,
    ``Chat`` or ``Channel``. Returns an empty string otherwise.
    """
    if isinstance(entity, User):
        if entity.last_name and entity.first_name:
            return '{} {}'.format(entity.first_name, entity.last_name)
        elif entity.first_name:
            return entity.first_name
        elif entity.last_name:
            return entity.last_name
        else:
            return ''

    elif isinstance(entity, (Chat, Channel)):
        return entity.title

    return ''

# For some reason, .webp (stickers' format) is not registered
add_type('image/webp', '.webp')


def get_extension(media):
    """Gets the corresponding extension for any Telegram media"""

    # Photos are always compressed as .jpg by Telegram
    if isinstance(media, (UserProfilePhoto, ChatPhoto, MessageMediaPhoto)):
        return '.jpg'

    # Documents will come with a mime type
    if isinstance(media, MessageMediaDocument):
        media = media.document
    if isinstance(media, Document):
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
    """Gets the input peer for the given "entity" (user, chat or channel).
       A TypeError is raised if the given entity isn't a supported type."""
    try:
        if entity.SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
            return entity
    except AttributeError:
        _raise_cast_fail(entity, 'InputPeer')

    if isinstance(entity, User):
        if entity.is_self and allow_self:
            return InputPeerSelf()
        else:
            return InputPeerUser(entity.id, entity.access_hash or 0)

    if isinstance(entity, (Chat, ChatEmpty, ChatForbidden)):
        return InputPeerChat(entity.id)

    if isinstance(entity, (Channel, ChannelForbidden)):
        return InputPeerChannel(entity.id, entity.access_hash or 0)

    # Less common cases
    if isinstance(entity, InputUser):
        return InputPeerUser(entity.user_id, entity.access_hash)

    if isinstance(entity, InputChannel):
        return InputPeerChannel(entity.channel_id, entity.access_hash)

    if isinstance(entity, InputUserSelf):
        return InputPeerSelf()

    if isinstance(entity, UserEmpty):
        return InputPeerEmpty()

    if isinstance(entity, UserFull):
        return get_input_peer(entity.user)

    if isinstance(entity, ChatFull):
        return InputPeerChat(entity.id)

    if isinstance(entity, PeerChat):
        return InputPeerChat(entity.chat_id)

    _raise_cast_fail(entity, 'InputPeer')


def get_input_channel(entity):
    """Similar to get_input_peer, but for InputChannel's alone"""
    try:
        if entity.SUBCLASS_OF_ID == 0x40f202fd:  # crc32(b'InputChannel')
            return entity
    except AttributeError:
        _raise_cast_fail(entity, 'InputChannel')

    if isinstance(entity, (Channel, ChannelForbidden)):
        return InputChannel(entity.id, entity.access_hash or 0)

    if isinstance(entity, InputPeerChannel):
        return InputChannel(entity.channel_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputChannel')


def get_input_user(entity):
    """Similar to get_input_peer, but for InputUser's alone"""
    try:
        if entity.SUBCLASS_OF_ID == 0xe669bf46:  # crc32(b'InputUser'):
            return entity
    except AttributeError:
        _raise_cast_fail(entity, 'InputUser')

    if isinstance(entity, User):
        if entity.is_self:
            return InputUserSelf()
        else:
            return InputUser(entity.id, entity.access_hash or 0)

    if isinstance(entity, InputPeerSelf):
        return InputUserSelf()

    if isinstance(entity, (UserEmpty, InputPeerEmpty)):
        return InputUserEmpty()

    if isinstance(entity, UserFull):
        return get_input_user(entity.user)

    if isinstance(entity, InputPeerUser):
        return InputUser(entity.user_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputUser')


def get_input_document(document):
    """Similar to get_input_peer, but for documents"""
    try:
        if document.SUBCLASS_OF_ID == 0xf33fdb68:  # crc32(b'InputDocument'):
            return document
    except AttributeError:
        _raise_cast_fail(document, 'InputDocument')

    if isinstance(document, Document):
        return InputDocument(id=document.id, access_hash=document.access_hash)

    if isinstance(document, DocumentEmpty):
        return InputDocumentEmpty()

    if isinstance(document, MessageMediaDocument):
        return get_input_document(document.document)

    if isinstance(document, Message):
        return get_input_document(document.media)

    _raise_cast_fail(document, 'InputDocument')


def get_input_photo(photo):
    """Similar to get_input_peer, but for documents"""
    try:
        if photo.SUBCLASS_OF_ID == 0x846363e0:  # crc32(b'InputPhoto'):
            return photo
    except AttributeError:
        _raise_cast_fail(photo, 'InputPhoto')

    if isinstance(photo, photos.Photo):
        photo = photo.photo

    if isinstance(photo, Photo):
        return InputPhoto(id=photo.id, access_hash=photo.access_hash)

    if isinstance(photo, PhotoEmpty):
        return InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


def get_input_geo(geo):
    """Similar to get_input_peer, but for geo points"""
    try:
        if geo.SUBCLASS_OF_ID == 0x430d225:  # crc32(b'InputGeoPoint'):
            return geo
    except AttributeError:
        _raise_cast_fail(geo, 'InputGeoPoint')

    if isinstance(geo, GeoPoint):
        return InputGeoPoint(lat=geo.lat, long=geo.long)

    if isinstance(geo, GeoPointEmpty):
        return InputGeoPointEmpty()

    if isinstance(geo, MessageMediaGeo):
        return get_input_geo(geo.geo)

    if isinstance(geo, Message):
        return get_input_geo(geo.media)

    _raise_cast_fail(geo, 'InputGeoPoint')


def get_input_media(media, is_photo=False):
    """Similar to get_input_peer, but for media.

       If the media is a file location and is_photo is known to be True,
       it will be treated as an InputMediaUploadedPhoto.
    """
    try:
        if media.SUBCLASS_OF_ID == 0xfaf846f4:  # crc32(b'InputMedia'):
            return media
    except AttributeError:
        _raise_cast_fail(media, 'InputMedia')

    if isinstance(media, MessageMediaPhoto):
        return InputMediaPhoto(
            id=get_input_photo(media.photo),
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, MessageMediaDocument):
        return InputMediaDocument(
            id=get_input_document(media.document),
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, FileLocation):
        if is_photo:
            return InputMediaUploadedPhoto(file=media)
        else:
            return InputMediaUploadedDocument(
                file=media,
                mime_type='application/octet-stream',  # unknown, assume bytes
                attributes=[DocumentAttributeFilename('unnamed')]
            )

    if isinstance(media, MessageMediaGame):
        return InputMediaGame(id=media.game.id)

    if isinstance(media, (ChatPhoto, UserProfilePhoto)):
        if isinstance(media.photo_big, FileLocationUnavailable):
            media = media.photo_small
        else:
            media = media.photo_big
        return get_input_media(media, is_photo=True)

    if isinstance(media, MessageMediaContact):
        return InputMediaContact(
            phone_number=media.phone_number,
            first_name=media.first_name,
            last_name=media.last_name
        )

    if isinstance(media, MessageMediaGeo):
        return InputMediaGeoPoint(geo_point=get_input_geo(media.geo))

    if isinstance(media, MessageMediaVenue):
        return InputMediaVenue(
            geo_point=get_input_geo(media.geo),
            title=media.title,
            address=media.address,
            provider=media.provider,
            venue_id=media.venue_id,
            venue_type=''
        )

    if isinstance(media, (
            MessageMediaEmpty, MessageMediaUnsupported,
            ChatPhotoEmpty, UserProfilePhotoEmpty, FileLocationUnavailable)):
        return InputMediaEmpty()

    if isinstance(media, Message):
        return get_input_media(media.media, is_photo=is_photo)

    _raise_cast_fail(media, 'InputMedia')


def is_image(file):
    """Returns True if the file extension looks like an image file"""
    return (isinstance(file, str) and
            (mimetypes.guess_type(file)[0] or '').startswith('image/'))


def is_audio(file):
    """Returns True if the file extension looks like an audio file"""
    return (isinstance(file, str) and
            (mimetypes.guess_type(file)[0] or '').startswith('audio/'))


def is_video(file):
    """Returns True if the file extension looks like a video file"""
    return (isinstance(file, str) and
            (mimetypes.guess_type(file)[0] or '').startswith('video/'))


def is_list_like(obj):
    """
    Returns True if the given object looks like a list.

    Checking if hasattr(obj, '__iter__') and ignoring str/bytes is not
    enough. Things like open() are also iterable (and probably many
    other things), so just support the commonly known list-like objects.
    """
    return isinstance(obj, (list, tuple, set, dict,
                            UserList, types.GeneratorType))


def parse_phone(phone):
    """Parses the given phone, or returns None if it's invalid"""
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

       Returns None if the username is not valid.
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


def get_peer_id(peer):
    """
    Finds the ID of the given peer, and converts it to the "bot api" format
    so it the peer can be identified back. User ID is left unmodified,
    chat ID is negated, and channel ID is prefixed with -100.

    The original ID and the peer type class can be returned with
    a call to utils.resolve_id(marked_id).
    """
    # First we assert it's a Peer TLObject, or early return for integers
    if isinstance(peer, int):
        return peer

    try:
        if peer.SUBCLASS_OF_ID not in (0x2d45687, 0xc91c90b6):
            if isinstance(peer, (ResolvedPeer, InputNotifyPeer, TopPeer)):
                peer = peer.peer
            else:
                # Not a Peer or an InputPeer, so first get its Input version
                peer = get_input_peer(peer, allow_self=False)
    except AttributeError:
        _raise_cast_fail(peer, 'int')

    # Set the right ID/kind, or raise if the TLObject is not recognised
    if isinstance(peer, (PeerUser, InputPeerUser)):
        return peer.user_id
    elif isinstance(peer, (PeerChat, InputPeerChat)):
        return -peer.chat_id
    elif isinstance(peer, (PeerChannel, InputPeerChannel, ChannelFull)):
        if isinstance(peer, ChannelFull):
            # Special case: .get_input_peer can't return InputChannel from
            # ChannelFull since it doesn't have an .access_hash attribute.
            i = peer.id
        else:
            i = peer.channel_id
        # Concat -100 through math tricks, .to_supergroup() on Madeline
        # IDs will be strictly positive -> log works
        return -(i + pow(10, math.floor(math.log10(i) + 3)))

    _raise_cast_fail(peer, 'int')


def resolve_id(marked_id):
    """Given a marked ID, returns the original ID and its Peer type"""
    if marked_id >= 0:
        return marked_id, PeerUser

    if str(marked_id).startswith('-100'):
        return int(str(marked_id)[4:]), PeerChannel

    return -marked_id, PeerChat


def get_appropriated_part_size(file_size):
    """Gets the appropriated part size when uploading or downloading files,
       given an initial file size"""
    if file_size <= 104857600:  # 100MB
        return 128
    if file_size <= 786432000:  # 750MB
        return 256
    if file_size <= 1572864000:  # 1500MB
        return 512

    raise ValueError('File size too large')
