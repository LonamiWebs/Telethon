from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types


@name_inner_event
class MessageDeleted(EventBuilder):
    """
    Event fired when one or more messages are deleted.
    """
    def build(self, update):
        if isinstance(update, types.UpdateDeleteMessages):
            event = MessageDeleted.Event(
                deleted_ids=update.messages,
                peer=None
            )
        elif isinstance(update, types.UpdateDeleteChannelMessages):
            event = MessageDeleted.Event(
                deleted_ids=update.messages,
                peer=types.PeerChannel(update.channel_id)
            )
        else:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(EventCommon):
        def __init__(self, deleted_ids, peer):
            super().__init__(
                chat_peer=peer, msg_id=(deleted_ids or [0])[0]
            )
            self.deleted_id = None if not deleted_ids else deleted_ids[0]
            self.deleted_ids = deleted_ids
