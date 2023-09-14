from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from ...session.message_box.adaptor import (
    update_short_chat_message,
    update_short_message,
)
from ...tl import abcs, types
from ..types import Message
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class NewMessage(Event, Message):
    """
    Occurs when a new message is sent or received.

    .. warning::

        Messages sent with the :class:`~telethon.Client` are also caught,
        so be careful not to enter infinite loops!
        This is true for all event types, including edits.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        if isinstance(update, (types.UpdateNewMessage, types.UpdateNewChannelMessage)):
            if isinstance(update.message, types.Message):
                return cls._from_raw(update.message)
        elif isinstance(
            update, (types.UpdateShortMessage, types.UpdateShortChatMessage)
        ):
            raise RuntimeError("should have been handled by adaptor")

        return None


class MessageEdited(Event):
    """
    Occurs when a new message is sent or received.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()


class MessageDeleted(Event):
    """
    Occurs when one or more messages are deleted.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()


class MessageRead(Event):
    """
    Occurs both when your messages are read by others, and when you read messages.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()
