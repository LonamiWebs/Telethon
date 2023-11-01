from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Self

from ...tl import abcs, types
from ..types import Chat, Message
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class NewMessage(Event, Message):
    """
    Occurs when a new message is sent or received.

    .. caution::

        Messages sent with the :class:`~telethon.Client` are also caught,
        so be careful not to enter infinite loops!
        This is true for all event types, including edits.
    """

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if isinstance(update.message, types.Message):
                return cls._from_raw(client, update.message, chat_map)
        elif isinstance(
            update, (types.UpdateShortMessage, types.UpdateShortChatMessage)
        ):
            raise RuntimeError("should have been handled by adaptor")

        return None


class MessageEdited(Event, Message):
    """
    Occurs when a new message is sent or received.
    """

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(
            update, (types.UpdateEditMessage, types.UpdateEditChannelMessage)
        ):
            return cls._from_raw(client, update.message, chat_map)
        else:
            return None


class MessageDeleted(Event):
    """
    Occurs when one or more messages are deleted.

    .. note::

        Telegram does not send the contents of the deleted messages.
        Because they are deleted, it's also impossible to fetch them.

        The chat is only known when the deletion occurs in broadcast channels or supergroups.
    """

    def __init__(self, msg_ids: List[int], channel_id: Optional[int]) -> None:
        self._msg_ids = msg_ids
        self._channel_id = channel_id

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateDeleteMessages):
            return cls._create(update.messages, None)
        elif isinstance(update, types.UpdateDeleteChannelMessages):
            return cls._create(update.messages, update.channel_id)
        else:
            return None


class MessageRead(Event):
    """
    Occurs both when your messages are read by others, and when you read messages.
    """

    def __init__(self, peer: abcs.Peer, max_id: int, out: bool) -> None:
        self._peer = peer
        self._max_id = max_id
        self._out = out

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateReadHistoryInbox):
            return cls._create(update.peer, update.max_id, False)
        elif isinstance(update, types.UpdateReadHistoryOutbox):
            return cls._create(update.peer, update.max_id, True)
        elif isinstance(update, types.UpdateReadChannelInbox):
            return cls._create(
                types.PeerChannel(channel_id=update.channel_id), update.max_id, False
            )
        elif isinstance(update, types.UpdateReadChannelOutbox):
            return cls._create(
                types.PeerChannel(channel_id=update.channel_id), update.max_id, True
            )
        else:
            return None
