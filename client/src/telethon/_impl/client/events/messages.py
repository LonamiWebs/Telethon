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
    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()


class MessageDeleted(Event):
    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()


class MessageRead(Event):
    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()
