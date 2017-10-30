"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like an User, Chat, etc. into its Input version)
"""
import math
from mimetypes import add_type, guess_extension

from .tl import TLObject
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
    FileLocationUnavailable, InputMediaUploadedDocument,
    InputMediaUploadedPhoto, DocumentAttributeFilename, photos
)


def get_display_name(entity):
    """Gets the input peer for the given "entity" (user, chat or channel)
       Returns None if it was not found"""
    if isinstance(entity, User):
        if entity.last_name and entity.first_name:
            return '{} {}'.format(entity.first_name, entity.last_name)
        elif entity.first_name:
            return entity.first_name
        elif entity.last_name:
            return entity.last_name
        else:
            return '(No name)'

    if isinstance(entity, (Chat, Channel)):
        return entity.title

    return '(unknown)'

# For some reason, .webp (stickers' format) is not registered
add_type('image/webp', '.webp')


def get_extension(media):
    """Gets the corresponding extension for any Telegram media"""

    # Photos are always compressed as .jpg by Telegram
    if isinstance(media, (UserProfilePhoto, ChatPhoto, MessageMediaPhoto)):
        return '.jpg'

    # Documents will come with a mime type
    if isinstance(media, MessageMediaDocument):
        if isinstance(media.document, Document):
            if media.document.mime_type == 'application/octet-stream':
                # Octet stream are just bytes, which have no default extension
                return ''
            else:
                extension = guess_extension(media.document.mime_type)
                return extension if extension else ''

    return ''


def _raise_cast_fail(entity, target):
    raise ValueError('Cannot cast {} to any kind of {}.'
                     .format(type(entity).__name__, target))


def get_input_peer(entity, allow_self=True):
    """Gets the input peer for the given "entity" (user, chat or channel).
       A ValueError is raised if the given entity isn't a supported type."""
    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputPeer')

    if type(entity).SUBCLASS_OF_ID == 0xc91c90b6:  # crc32(b'InputPeer')
        return entity

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
    if isinstance(entity, UserEmpty):
        return InputPeerEmpty()

    if isinstance(entity, InputUser):
        return InputPeerUser(entity.user_id, entity.access_hash)

    if isinstance(entity, UserFull):
        return get_input_peer(entity.user)

    if isinstance(entity, ChatFull):
        return InputPeerChat(entity.id)

    if isinstance(entity, PeerChat):
        return InputPeerChat(entity.chat_id)

    _raise_cast_fail(entity, 'InputPeer')


def get_input_channel(entity):
    """Similar to get_input_peer, but for InputChannel's alone"""
    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputChannel')

    if type(entity).SUBCLASS_OF_ID == 0x40f202fd:  # crc32(b'InputChannel')
        return entity

    if isinstance(entity, (Channel, ChannelForbidden)):
        return InputChannel(entity.id, entity.access_hash or 0)

    if isinstance(entity, InputPeerChannel):
        return InputChannel(entity.channel_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputChannel')


def get_input_user(entity):
    """Similar to get_input_peer, but for InputUser's alone"""
    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputUser')

    if type(entity).SUBCLASS_OF_ID == 0xe669bf46:  # crc32(b'InputUser')
        return entity

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
    if not isinstance(document, TLObject):
        _raise_cast_fail(document, 'InputDocument')

    if type(document).SUBCLASS_OF_ID == 0xf33fdb68:  # crc32(b'InputDocument')
        return document

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
    if not isinstance(photo, TLObject):
        _raise_cast_fail(photo, 'InputPhoto')

    if type(photo).SUBCLASS_OF_ID == 0x846363e0:  # crc32(b'InputPhoto')
        return photo

    if isinstance(photo, photos.Photo):
        photo = photo.photo

    if isinstance(photo, Photo):
        return InputPhoto(id=photo.id, access_hash=photo.access_hash)

    if isinstance(photo, PhotoEmpty):
        return InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


def get_input_geo(geo):
    """Similar to get_input_peer, but for geo points"""
    if not isinstance(geo, TLObject):
        _raise_cast_fail(geo, 'InputGeoPoint')

    if type(geo).SUBCLASS_OF_ID == 0x430d225:  # crc32(b'InputGeoPoint')
        return geo

    if isinstance(geo, GeoPoint):
        return InputGeoPoint(lat=geo.lat, long=geo.long)

    if isinstance(geo, GeoPointEmpty):
        return InputGeoPointEmpty()

    if isinstance(geo, MessageMediaGeo):
        return get_input_geo(geo.geo)

    if isinstance(geo, Message):
        return get_input_geo(geo.media)

    _raise_cast_fail(geo, 'InputGeoPoint')


def get_input_media(media, user_caption=None, is_photo=False):
    """Similar to get_input_peer, but for media.

       If the media is a file location and is_photo is known to be True,
       it will be treated as an InputMediaUploadedPhoto.
    """
    if not isinstance(media, TLObject):
        _raise_cast_fail(media, 'InputMedia')

    if type(media).SUBCLASS_OF_ID == 0xfaf846f4:  # crc32(b'InputMedia')
        return media

    if isinstance(media, MessageMediaPhoto):
        return InputMediaPhoto(
            id=get_input_photo(media.photo),
            caption=media.caption if user_caption is None else user_caption,
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, MessageMediaDocument):
        return InputMediaDocument(
            id=get_input_document(media.document),
            caption=media.caption if user_caption is None else user_caption,
            ttl_seconds=media.ttl_seconds
        )

    if isinstance(media, FileLocation):
        if is_photo:
            return InputMediaUploadedPhoto(
                file=media,
                caption=user_caption or ''
            )
        else:
            return InputMediaUploadedDocument(
                file=media,
                mime_type='application/octet-stream',  # unknown, assume bytes
                attributes=[DocumentAttributeFilename('unnamed')],
                caption=user_caption or ''
            )

    if isinstance(media, MessageMediaGame):
        return InputMediaGame(id=media.game.id)

    if isinstance(media, (ChatPhoto, UserProfilePhoto)):
        if isinstance(media.photo_big, FileLocationUnavailable):
            return get_input_media(media.photo_small, is_photo=True)
        else:
            return get_input_media(media.photo_big, is_photo=True)

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
            venue_id=media.venue_id
        )

    if isinstance(media, (
            MessageMediaEmpty, MessageMediaUnsupported,
            ChatPhotoEmpty, UserProfilePhotoEmpty, FileLocationUnavailable)):
        return InputMediaEmpty()

    if isinstance(media, Message):
        return get_input_media(media.media)

    _raise_cast_fail(media, 'InputMedia')


def get_peer_id(peer, add_mark=False):
    """Finds the ID of the given peer, and optionally converts it to
       the "bot api" format if 'add_mark' is set to True.
    """
    # First we assert it's a Peer TLObject, or early return for integers
    if not isinstance(peer, TLObject):
        if isinstance(peer, int):
            return peer
        else:
            _raise_cast_fail(peer, 'int')

    elif type(peer).SUBCLASS_OF_ID not in {0x2d45687, 0xc91c90b6}:
        # Not a Peer or an InputPeer, so first get its Input version
        peer = get_input_peer(peer, allow_self=False)

    # Set the right ID/kind, or raise if the TLObject is not recognised
    if isinstance(peer, (PeerUser, InputPeerUser)):
        return peer.user_id
    elif isinstance(peer, (PeerChat, InputPeerChat)):
        return -peer.chat_id if add_mark else peer.chat_id
    elif isinstance(peer, (PeerChannel, InputPeerChannel)):
        i = peer.channel_id
        if add_mark:
            # Concat -100 through math tricks, .to_supergroup() on Madeline
            # IDs will be strictly positive -> log works
            return -(i + pow(10, math.floor(math.log10(i) + 3)))
        else:
            return i

    _raise_cast_fail(peer, 'int')


def resolve_id(marked_id):
    """Given a marked ID, returns the original ID and its Peer type"""
    if marked_id >= 0:
        return marked_id, PeerUser

    if str(marked_id).startswith('-100'):
        return int(str(marked_id)[4:]), PeerChannel

    return -marked_id, PeerChat


def find_user_or_chat(peer, users, chats):
    """Finds the corresponding user or chat given a peer.
       Returns None if it was not found"""
    if isinstance(peer, PeerUser):
        peer, where = peer.user_id, users
    else:
        where = chats
        if isinstance(peer, PeerChat):
            peer = peer.chat_id
        elif isinstance(peer, PeerChannel):
            peer = peer.channel_id

    if isinstance(peer, int):
        if isinstance(where, dict):
            return where.get(peer)
        else:
            try:
                return next(x for x in where if x.id == peer)
            except StopIteration:
                pass


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
