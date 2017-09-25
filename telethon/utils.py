"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like an User, Chat, etc. into its Input version)
"""
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
    InputMediaUploadedPhoto,
    DocumentAttributeFilename)


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

    if isinstance(entity, Chat) or isinstance(entity, Channel):
        return entity.title

    return '(unknown)'

# For some reason, .webp (stickers' format) is not registered
add_type('image/webp', '.webp')


def get_extension(media):
    """Gets the corresponding extension for any Telegram media"""

    # Photos are always compressed as .jpg by Telegram
    if (isinstance(media, UserProfilePhoto) or isinstance(media, ChatPhoto) or
            isinstance(media, MessageMediaPhoto)):
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


def get_input_peer(entity):
    """Gets the input peer for the given "entity" (user, chat or channel).
       A ValueError is raised if the given entity isn't a supported type."""
    if entity is None:
        return None

    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputPeer')

    if type(entity).subclass_of_id == 0xc91c90b6:  # crc32(b'InputPeer')
        return entity

    if isinstance(entity, User):
        if entity.is_self:
            return InputPeerSelf()
        else:
            return InputPeerUser(entity.id, entity.access_hash)

    if any(isinstance(entity, c) for c in (
            Chat, ChatEmpty, ChatForbidden)):
        return InputPeerChat(entity.id)

    if any(isinstance(entity, c) for c in (
            Channel, ChannelForbidden)):
        return InputPeerChannel(entity.id, entity.access_hash)

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
    if entity is None:
        return None

    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputChannel')

    if type(entity).subclass_of_id == 0x40f202fd:  # crc32(b'InputChannel')
        return entity

    if isinstance(entity, Channel) or isinstance(entity, ChannelForbidden):
        return InputChannel(entity.id, entity.access_hash)

    if isinstance(entity, InputPeerChannel):
        return InputChannel(entity.channel_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputChannel')


def get_input_user(entity):
    """Similar to get_input_peer, but for InputUser's alone"""
    if entity is None:
        return None

    if not isinstance(entity, TLObject):
        _raise_cast_fail(entity, 'InputUser')

    if type(entity).subclass_of_id == 0xe669bf46:  # crc32(b'InputUser')
        return entity

    if isinstance(entity, User):
        if entity.is_self:
            return InputUserSelf()
        else:
            return InputUser(entity.id, entity.access_hash)

    if isinstance(entity, UserEmpty):
        return InputUserEmpty()

    if isinstance(entity, UserFull):
        return get_input_user(entity.user)

    if isinstance(entity, InputPeerUser):
        return InputUser(entity.user_id, entity.access_hash)

    _raise_cast_fail(entity, 'InputUser')


def get_input_document(document):
    """Similar to get_input_peer, but for documents"""
    if document is None:
        return None

    if not isinstance(document, TLObject):
        _raise_cast_fail(document, 'InputDocument')

    if type(document).subclass_of_id == 0xf33fdb68:  # crc32(b'InputDocument')
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
    if photo is None:
        return None

    if not isinstance(photo, TLObject):
        _raise_cast_fail(photo, 'InputPhoto')

    if type(photo).subclass_of_id == 0x846363e0:  # crc32(b'InputPhoto')
        return photo

    if isinstance(photo, Photo):
        return InputPhoto(id=photo.id, access_hash=photo.access_hash)

    if isinstance(photo, PhotoEmpty):
        return InputPhotoEmpty()

    _raise_cast_fail(photo, 'InputPhoto')


def get_input_geo(geo):
    """Similar to get_input_peer, but for geo points"""
    if geo is None:
        return None

    if not isinstance(geo, TLObject):
        _raise_cast_fail(geo, 'InputGeoPoint')

    if type(geo).subclass_of_id == 0x430d225:  # crc32(b'InputGeoPoint')
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
    if media is None:
        return None

    if not isinstance(media, TLObject):
        _raise_cast_fail(media, 'InputMedia')

    if type(media).subclass_of_id == 0xfaf846f4:  # crc32(b'InputMedia')
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

    if isinstance(media, ChatPhoto) or isinstance(media, UserProfilePhoto):
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

    if any(isinstance(media, t) for t in (
            MessageMediaEmpty, MessageMediaUnsupported,
            FileLocationUnavailable, ChatPhotoEmpty,
            UserProfilePhotoEmpty)):
        return InputMediaEmpty()

    if isinstance(media, Message):
        return get_input_media(media.media)

    _raise_cast_fail(media, 'InputMedia')


def find_user_or_chat(peer, users, chats):
    """Finds the corresponding user or chat given a peer.
       Returns None if it was not found"""
    try:
        if isinstance(peer, PeerUser):
            return next(u for u in users if u.id == peer.user_id)

        elif isinstance(peer, PeerChat):
            return next(c for c in chats if c.id == peer.chat_id)

        elif isinstance(peer, PeerChannel):
            return next(c for c in chats if c.id == peer.channel_id)

    except StopIteration: return

    if isinstance(peer, int):
        try: return next(u for u in users if u.id == peer)
        except StopIteration: pass

        try: return next(c for c in chats if c.id == peer)
        except StopIteration: pass


def get_appropriated_part_size(file_size):
    """Gets the appropriated part size when uploading or downloading files,
       given an initial file size"""
    if file_size <= 1048576:  # 1MB
        return 32
    if file_size <= 10485760:  # 10MB
        return 64
    if file_size <= 393216000:  # 375MB
        return 128
    if file_size <= 786432000:  # 750MB
        return 256
    if file_size <= 1572864000:  # 1500MB
        return 512

    raise ValueError('File size too large')
