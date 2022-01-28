import abc


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
    def _build(cls, update, others, self_id, entities, client):
        """
        Builds an event for the given update if possible, or returns None.

        `others` are the rest of updates that came in the same container
        as the current `update`.

        `self_id` should be the current user's ID, since it is required
        for some events which lack this information but still need it.
        """
