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
    PeerChat, PeerUser, User, UserFull, UserProfilePhoto, Document
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
