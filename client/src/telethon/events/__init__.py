"""
Classes related to the different event types that wrap incoming Telegram updates.

See the :doc:`/concepts/updates` concept for more details.
"""
from .._impl.client.events import (
    CallbackQuery,
    Event,
    InlineQuery,
    MessageDeleted,
    MessageEdited,
    MessageRead,
    NewMessage,
)

__all__ = [
    "CallbackQuery",
    "Event",
    "InlineQuery",
    "MessageDeleted",
    "MessageEdited",
    "MessageRead",
    "NewMessage",
]
