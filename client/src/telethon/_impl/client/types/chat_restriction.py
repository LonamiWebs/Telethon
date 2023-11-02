from __future__ import annotations

from enum import Enum
from typing import Set

from ...tl import abcs, types


class ChatRestriction(Enum):
    """
    A restriction that may be applied to a banned chat's participant.

    A banned participant is completley banned from a chat if they are forbidden to :attr:`VIEW_MESSAGES`.

    A banned participant that can :attr:`VIEW_MESSAGES` is restricted, but can still be part of the chat,

    .. note::

        The specific values of the enumeration are not covered by `semver <https://semver.org/>`_.
        They also may do nothing in future updates if Telegram decides to change them.
    """

    VIEW_MESSAGES = "view_messages"
    """
    Prevents being in the chat and fetching the message history.

    Applying this restriction will kick the participant out of the group.
    """

    SEND_MESSAGES = "send_messages"
    """Prevents sending messages to the chat."""

    SEND_MEDIA = "send_media"
    """Prevents sending messages with media such as photos or documents to the chat."""

    SEND_STICKERS = "send_stickers"
    """Prevents sending sticker media to the chat."""

    SEND_GIFS = "send_gifs"
    """Prevents sending muted looping video media ("GIFs") to the chat."""

    SEND_GAMES = "send_games"
    """Prevents sending *@bot inline* games to the chat."""

    SEND_INLINE = "send_inline"
    """Prevents sending messages via *@bot inline* to the chat."""

    EMBED_LINKS = "embed_links"
    """Prevents sending messages that include links to external URLs to the chat."""

    SEND_POLLS = "send_polls"
    """Prevents sending poll media to the chat."""

    CHANGE_INFO = "change_info"
    """Prevents changing the description of the chat."""

    INVITE_USERS = "invite_users"
    """Prevents inviting users to the chat."""

    PIN_MESSAGES = "pin_messages"
    """Prevents pinning messages to the chat."""

    MANAGE_TOPICS = "manage_topics"
    """Prevents managing the topics of the chat."""

    SEND_PHOTOS = "send_photos"
    """Prevents sending photo media files to the chat."""

    SEND_VIDEOS = "send_videos"
    """Prevents sending video media files to the chat."""

    SEND_ROUND_VIDEOS = "send_roundvideos"
    """Prevents sending round video media files to the chat."""

    SEND_AUDIOS = "send_audios"
    """Prevents sending audio media files to the chat."""

    SEND_VOICE_NOTES = "send_voices"
    """Prevents sending voice note audio media files to the chat."""

    SEND_DOCUMENTS = "send_docs"
    """Prevents sending document media files to the chat."""

    SEND_PLAIN_MESSAGES = "send_plain"
    """Prevents sending plain text messages with no media to the chat."""

    @classmethod
    def _from_raw(cls, rights: abcs.ChatBannedRights) -> Set[ChatRestriction]:
        assert isinstance(rights, types.ChatBannedRights)
        restrictions = (
            cls.VIEW_MESSAGES if rights.view_messages else None,
            cls.SEND_MESSAGES if rights.send_messages else None,
            cls.SEND_MEDIA if rights.send_media else None,
            cls.SEND_STICKERS if rights.send_stickers else None,
            cls.SEND_GIFS if rights.send_gifs else None,
            cls.SEND_GAMES if rights.send_games else None,
            cls.SEND_INLINE if rights.send_inline else None,
            cls.EMBED_LINKS if rights.embed_links else None,
            cls.SEND_POLLS if rights.send_polls else None,
            cls.CHANGE_INFO if rights.change_info else None,
            cls.INVITE_USERS if rights.invite_users else None,
            cls.PIN_MESSAGES if rights.pin_messages else None,
            cls.MANAGE_TOPICS if rights.manage_topics else None,
            cls.SEND_PHOTOS if rights.send_photos else None,
            cls.SEND_VIDEOS if rights.send_videos else None,
            cls.SEND_ROUND_VIDEOS if rights.send_roundvideos else None,
            cls.SEND_AUDIOS if rights.send_audios else None,
            cls.SEND_VOICE_NOTES if rights.send_voices else None,
            cls.SEND_DOCUMENTS if rights.send_docs else None,
            cls.SEND_PLAIN_MESSAGES if rights.send_plain else None,
        )
        return set(filter(None, iter(restrictions)))

    @classmethod
    def _set_to_raw(
        cls, restrictions: Set[ChatRestriction], until_date: int
    ) -> types.ChatBannedRights:
        return types.ChatBannedRights(
            view_messages=cls.VIEW_MESSAGES in restrictions,
            send_messages=cls.SEND_MESSAGES in restrictions,
            send_media=cls.SEND_MEDIA in restrictions,
            send_stickers=cls.SEND_STICKERS in restrictions,
            send_gifs=cls.SEND_GIFS in restrictions,
            send_games=cls.SEND_GAMES in restrictions,
            send_inline=cls.SEND_INLINE in restrictions,
            embed_links=cls.EMBED_LINKS in restrictions,
            send_polls=cls.SEND_POLLS in restrictions,
            change_info=cls.CHANGE_INFO in restrictions,
            invite_users=cls.INVITE_USERS in restrictions,
            pin_messages=cls.PIN_MESSAGES in restrictions,
            manage_topics=cls.MANAGE_TOPICS in restrictions,
            send_photos=cls.SEND_PHOTOS in restrictions,
            send_videos=cls.SEND_VIDEOS in restrictions,
            send_roundvideos=cls.SEND_ROUND_VIDEOS in restrictions,
            send_audios=cls.SEND_AUDIOS in restrictions,
            send_voices=cls.SEND_VOICE_NOTES in restrictions,
            send_docs=cls.SEND_DOCUMENTS in restrictions,
            send_plain=cls.SEND_PLAIN_MESSAGES in restrictions,
            until_date=until_date,
        )
