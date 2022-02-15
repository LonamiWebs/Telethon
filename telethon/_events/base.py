import abc
import functools

from .filters import Filter


class StopPropagation(Exception):
    """
    If this exception is raised in any of the handlers for a given event,
    it will stop the execution of all other registered event handlers.
    It can be seen as the ``StopIteration`` in a for loop but for events.

    Example usage:

        >>> from telethon import TelegramClient, events
        >>> client = TelegramClient(...)
        >>>
        >>> @client.on(events.NewMessage)
        ... async def delete(event):
        ...     await event.delete()
        ...     # No other event handler will have a chance to handle this event
        ...     raise StopPropagation
        ...
        >>> @client.on(events.NewMessage)
        ... async def _(event):
        ...     # Will never be reached, because it is the second handler
        ...     pass
    """
    # For some reason Sphinx wants the silly >>> or
    # it will show warnings and look bad when generated.
    pass


class EventBuilder(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def _build(cls, client, update, entities):
        """
        Builds an event for the given update if possible, or returns None.

        `entities` must have `get(Peer) -> User|Chat` and `self_id`,
        which must be the current user's ID.
        """


@functools.total_ordering
class EventHandler:
    __slots__ = ('_event', '_callback', '_priority', '_filter')

    def __init__(self, event: EventBuilder, callback: callable, priority: int, filter: Filter):
        self._event = event
        self._callback = callback
        self._priority = priority
        self._filter = filter

    def __eq__(self, other):
        return self is other

    def __lt__(self, other):
        return self._priority < other._priority

    def __call__(self, *args, **kwargs):
        return self._callback(*args, **kwargs)
