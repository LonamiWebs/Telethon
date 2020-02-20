from .common import EventBuilder, EventCommon, name_inner_event
from ..tl import types


@name_inner_event
class MessageDeleted(EventBuilder):
    """
    Occurs whenever a message is deleted. Note that this event isn't 100%
    reliable, since Telegram doesn't always notify the clients that a message
    was deleted.

    .. important::

        Telegram **does not** send information about *where* a message
        was deleted if it occurs in private conversations with other users
        or in small group chats, because message IDs are *unique* and you
        can identify the chat with the message ID alone if you saved it
        previously.

        Telethon **does not** save information of where messages occur,
        so it cannot know in which chat a message was deleted (this will
        only work in channels, where the channel ID *is* present).

        This means that the ``chats=`` parameter will not work reliably,
        unless you intend on working with channels and super-groups only.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.MessageDeleted)
            async def handler(event):
                # Log all deleted message IDs
                for msg_id in event.deleted_ids:
                    print('Message', msg_id, 'was deleted in', event.chat_id)
    """
    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateDeleteMessages):
            return cls.Event(
                deleted_ids=update.messages,
                peer=None
            )
        elif isinstance(update, types.UpdateDeleteChannelMessages):
            return cls.Event(
                deleted_ids=update.messages,
                peer=types.PeerChannel(update.channel_id)
            )

    class Event(EventCommon):
        def __init__(self, deleted_ids, peer):
            super().__init__(
                chat_peer=peer, msg_id=(deleted_ids or [0])[0]
            )
            self.deleted_id = None if not deleted_ids else deleted_ids[0]
            self.deleted_ids = deleted_ids
