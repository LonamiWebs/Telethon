"""Utilities for working with TLObjects.
   We have these because some TLObjects differ in very little things,
   for example, some may have an `user_id` attribute and other a `chat_id` but,
   after all, both are the same attribute, IDs."""
from mimetypes import add_type, guess_extension

from ..tl.types import (
    Channel, Chat, ChatPhoto, InputPeerChannel, InputPeerChat, InputPeerUser,
    MessageMediaDocument, MessageMediaPhoto, PeerChannel, PeerChat, PeerUser,
    User, UserProfilePhoto)


def get_display_name(entity):
    """Gets the input peer for the given "entity" (user, chat or channel)
       Returns None if it was not found"""
    if isinstance(entity, User):
        if entity.last_name is not None:
            return '{} {}'.format(entity.first_name, entity.last_name)
        return entity.first_name

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
    if (isinstance(entity, InputPeerUser) or
        isinstance(entity, InputPeerChat) or
            isinstance(entity, InputPeerChannel)):
        return entity

    if isinstance(entity, User):
        return InputPeerUser(entity.id, entity.access_hash)
    if isinstance(entity, Chat):
        return InputPeerChat(entity.id)
    if isinstance(entity, Channel):
        return InputPeerChannel(entity.id, entity.access_hash)

    raise ValueError('Cannot cast {} to any kind of InputPeer.'
                     .format(type(entity).__name__))


def find_user_or_chat(peer, users, chats):
    """Finds the corresponding user or chat given a peer.
       Returns None if it was not found"""
    try:
        if isinstance(peer, PeerUser):
            user = next(u for u in users if u.id == peer.user_id)
            return user

        elif isinstance(peer, PeerChat):
            chat = next(c for c in chats if c.id == peer.chat_id)
            return chat

        elif isinstance(peer, PeerChannel):
            channel = next(c for c in chats if c.id == peer.channel_id)
            return channel

    except StopIteration:
        return None


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
