from .raw import Raw
from .album import Album
from .chataction import ChatAction
from .messagedeleted import MessageDeleted
from .messageedited import MessageEdited
from .messageread import MessageRead
from .newmessage import NewMessage
from .userupdate import UserUpdate
from .callbackquery import CallbackQuery
from .inlinequery import InlineQuery


_HANDLERS_ATTRIBUTE = '__tl.handlers'


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


def register(event=None):
    """
    Decorator method to *register* event handlers. This is the client-less
    `add_event_handler()
    <telethon.client.updates.UpdateMethods.add_event_handler>` variant.

    Note that this method only registers callbacks as handlers,
    and does not attach them to any client. This is useful for
    external modules that don't have access to the client, but
    still want to define themselves as a handler. Example:

    >>> from telethon import events
    >>> @events.register(events.NewMessage)
    ... async def handler(event):
    ...     ...
    ...
    >>> # (somewhere else)
    ...
    >>> from telethon import TelegramClient
    >>> client = TelegramClient(...)
    >>> client.add_event_handler(handler)

    Remember that you can use this as a non-decorator
    through ``register(event)(callback)``.

    Args:
        event (`_EventBuilder` | `type`):
            The event builder class or instance to be used,
            for instance ``events.NewMessage``.
    """
    if isinstance(event, type):
        event = event()
    elif not event:
        event = Raw()

    def decorator(callback):
        handlers = getattr(callback, _HANDLERS_ATTRIBUTE, [])
        handlers.append(event)
        setattr(callback, _HANDLERS_ATTRIBUTE, handlers)
        return callback

    return decorator


def unregister(callback, event=None):
    """
    Inverse operation of `register` (though not a decorator). Client-less
    `remove_event_handler
    <telethon.client.updates.UpdateMethods.remove_event_handler>`
    variant. **Note that this won't remove handlers from the client**,
    because it simply can't, so you would generally use this before
    adding the handlers to the client.

    This method is here for symmetry. You will rarely need to
    unregister events, since you can simply just not add them
    to any client.

    If no event is given, all events for this callback are removed.
    Returns how many callbacks were removed.
    """
    found = 0
    if event and not isinstance(event, type):
        event = type(event)

    handlers = getattr(callback, _HANDLERS_ATTRIBUTE, [])
    handlers.append((event, callback))
    i = len(handlers)
    while i:
        i -= 1
        ev = handlers[i]
        if not event or isinstance(ev, event):
            del handlers[i]
            found += 1

    return found


def is_handler(callback):
    """
    Returns `True` if the given callback is an
    event handler (i.e. you used `register` on it).
    """
    return hasattr(callback, _HANDLERS_ATTRIBUTE)


def list(callback):
    """
    Returns a list containing the registered event
    builders inside the specified callback handler.
    """
    return getattr(callback, _HANDLERS_ATTRIBUTE, [])[:]


def _get_handlers(callback):
    """
    Like ``list`` but returns `None` if the callback was never registered.
    """
    return getattr(callback, _HANDLERS_ATTRIBUTE, None)
