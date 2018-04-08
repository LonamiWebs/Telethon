from .common import name_inner_event
from .newmessage import NewMessage
from ..tl import types


@name_inner_event
class MessageEdited(NewMessage):
    """
    Event fired when a message has been edited.
    """
    def build(self, update):
        if isinstance(update, (types.UpdateEditMessage,
                               types.UpdateEditChannelMessage)):
            event = MessageEdited.Event(update.message)
        else:
            return

        event._entities = update._entities
        return self._message_filter_event(event)

    class Event(NewMessage.Event):
        pass  # Required if we want a different name for it
