"""
Filters are functions that accept a single parameter, an :class:`~telethon.events.Event` instance, and return a :class:`bool`.

When the return value is :data:`True`, the associated :mod:`~telethon.events` handler will be invoked.

.. seealso::

    The :doc:`/concepts/updates` concept to learn to combine filters or define your own.
"""
from .._impl.client.events.filters import (
    All,
    Any,
    Chats,
    Command,
    Filter,
    Forward,
    Incoming,
    Media,
    Not,
    Outgoing,
    Reply,
    Senders,
    Text,
    TextOnly,
)

__all__ = [
    "All",
    "Any",
    "Chats",
    "Command",
    "Filter",
    "Forward",
    "Incoming",
    "Media",
    "Not",
    "Outgoing",
    "Reply",
    "Senders",
    "Text",
    "TextOnly",
]
