"""
Utilities for working with the Telegram API itself (such as handy methods
to convert between an entity like an User, Chat, etc. into its Input version)
"""
from mimetypes import add_type, guess_extension

from .tl.types import (
    Channel, ChannelForbidden, Chat, ChatEmpty, ChatForbidden, ChatFull,
    ChatPhoto, InputPeerChannel, InputPeerChat, InputPeerUser, InputPeerEmpty,
    InputPeerSelf, MessageMediaDocument, MessageMediaPhoto, PeerChannel,
    PeerChat, PeerUser, User, UserFull, UserProfilePhoto)


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

    # Documents will come with a mime type, from which we can guess their mime type
    if isinstance(media, MessageMediaDocument):
        extension = guess_extension(media.document.mime_type)
        return extension if extension else ''

    return None


def get_input_peer(entity):
    """Gets the input peer for the given "entity" (user, chat or channel).
       A ValueError is raised if the given entity isn't a supported type."""
    if type(entity).subclass_of_id == 0xc91c90b6:  # crc32('InputUser')
        return entity

    if isinstance(entity, User):
        return InputPeerUser(entity.id, entity.access_hash)

    if any(isinstance(entity, c) for c in (
            Chat, ChatEmpty, ChatForbidden)):
        return InputPeerChat(entity.id)

    if any(isinstance(entity, c) for c in (
            Channel, ChannelForbidden)):
        return InputPeerChannel(entity.id, entity.access_hash)

    # Less common cases
    if isinstance(entity, UserFull):
        return InputPeerUser(entity.user.id, entity.user.access_hash)

    if isinstance(entity, ChatFull):
        return InputPeerChat(entity.id)

    raise ValueError('Cannot cast {} to any kind of InputPeer.'
                     .format(type(entity).__name__))


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
