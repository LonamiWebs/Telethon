from .common import name_inner_event
from .newmessage import NewMessage
from ..tl import types


@name_inner_event
class MessageEdited(NewMessage):
    """
    Occurs whenever a message is edited. Just like `NewMessage
    <telethon.events.newmessage.NewMessage>`, you should treat
    this event as a `Message <telethon.tl.custom.message.Message>`.

    .. warning::

        On channels, `Message.out <telethon.tl.custom.message.Message>`
        will be ``True`` if you sent the message originally, **not if
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
    """
    @classmethod
    def build(cls, update):
        if isinstance(update, (types.UpdateEditMessage,
                               types.UpdateEditChannelMessage)):
            event = cls.Event(update.message)
        else:
            return

        event._entities = update._entities
        return event

    class Event(NewMessage.Event):
        pass  # Required if we want a different name for it
