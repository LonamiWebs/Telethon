from .common import name_inner_event
from .newmessage import NewMessage
from ..tl import types


@name_inner_event
class MessageEdited(NewMessage):
    """
    Event fired when a message has been edited.
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
