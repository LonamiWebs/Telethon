from .raw import Raw
from .chataction import ChatAction
from .messagedeleted import MessageDeleted
from .messageedited import MessageEdited
from .messageread import MessageRead
from .newmessage import NewMessage
from .userupdate import UserUpdate
from .callbackquery import CallbackQuery
from .inlinequery import InlineQuery


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
