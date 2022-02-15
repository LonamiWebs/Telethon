from .base import EventBuilder
from .. import _tl


class MessageEdited(EventBuilder):
    """
    Occurs whenever a message is edited. Just like `NewMessage
    <telethon.events.newmessage.NewMessage>`, you should treat
    this event as a `Message <telethon.tl.custom.message.Message>`.

    .. warning::

        On channels, `Message.out <telethon.tl.custom.message.Message>`
        will be `True` if you sent the message originally, **not if
        you edited it**! This can be dangerous if you run outgoing
        commands on edits.

        Some examples follow:

        * You send a message "A", ``out is True``.
        * You edit "A" to "B", ``out is True``.
        * Someone else edits "B" to "C", ``out is True`` (**be careful!**).
        * Someone sends "X", ``out is False``.
        * Someone edits "X" to "Y", ``out is False``.
        * You edit "Y" to "Z", ``out is False``.

        Since there are useful cases where you need the right ``out``
        value, the library cannot do anything automatically to help you.
        Instead, consider using ``from_users='me'`` (it won't work in
        broadcast channels at all since the sender is the channel and
        not you).

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.MessageEdited)
            async def handler(event):
                # Log the date of new edits
                print('Message', event.id, 'changed at', event.date)
    """
    @classmethod
    def _build(cls, client, update, entities):
        if isinstance(update, (_tl.UpdateEditMessage,
                               _tl.UpdateEditChannelMessage)):
            return cls._new(client, update.message, entities, None)
