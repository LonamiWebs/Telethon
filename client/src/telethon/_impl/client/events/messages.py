from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Self, Sequence, Union

from ...tl import abcs, types
from ..types import Chat, Message, expand_peer, peer_id
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class NewMessage(Event, Message):
    """
    Occurs when a new message is sent or received.

    This event can be treated as the :class:`~telethon.types.Message` itself.

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

    This event can be treated as the :class:`~telethon.types.Message` itself.
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

    def __init__(self, msg_ids: Sequence[int], channel_id: Optional[int]) -> None:
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

    @property
    def message_ids(self) -> Sequence[int]:
        """
        The message identifiers of the messages that were deleted.
        """
        return self._msg_ids

    @property
    def channel_id(self) -> Optional[int]:
        """
        The channel identifier of the supergroup or broadcast channel where the messages were deleted.

        This will be :data:`None` if the messages were deleted anywhere else.
        """
        return self._channel_id


class MessageRead(Event):
    """
    Occurs both when your messages are read by others, and when you read messages.
    """

    def __init__(
        self,
        client: Client,
        update: Union[
            types.UpdateReadHistoryInbox,
            types.UpdateReadHistoryOutbox,
            types.UpdateReadChannelInbox,
            types.UpdateReadChannelOutbox,
        ],
        chat_map: Dict[int, Chat],
    ) -> None:
        self._client = client
        self._raw = update
        self._chat_map = chat_map

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(
            update,
            (
                types.UpdateReadHistoryInbox,
                types.UpdateReadHistoryOutbox,
                types.UpdateReadChannelInbox,
                types.UpdateReadChannelOutbox,
            ),
        ):
            return cls._create(client, update, chat_map)
        else:
            return None

    def _peer(self) -> abcs.Peer:
        if isinstance(
            self._raw, (types.UpdateReadHistoryInbox, types.UpdateReadHistoryOutbox)
        ):
            return self._raw.peer
        else:
            return types.PeerChannel(channel_id=self._raw.channel_id)

    @property
    def chat(self) -> Chat:
        """
        The :term:`chat` when the messages were read.
        """
        peer = self._peer()
        pid = peer_id(peer)
        if pid not in self._chat_map:
            self._chat_map[pid] = expand_peer(
                self._client, peer, broadcast=getattr(self._raw, "post", None)
            )
        return self._chat_map[pid]

    @property
    def max_message_id_read(self) -> int:
        """
        The highest message identifier of the messages that have been marked as read.

        In other words, messages with an identifier below or equal (``<=``) to this value are considered read.
        Messages with an identifier higher (``>``) to this value are considered unread.

        .. rubric:: Example

        .. code-block:: python

            if message.id <= event.max_message_id_read:
                print('message is marked as read')
            else:
                print('message is not yet marked as read')
        """
        return self._raw.max_id
