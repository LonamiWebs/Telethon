"""
Classes related to the different event types that wrap incoming Telegram updates.

.. seealso::

    The :doc:`/concepts/updates` concept to learn how to listen to these events.
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
