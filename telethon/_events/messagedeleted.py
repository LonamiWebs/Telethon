from .base import EventBuilder
from .. import _tl
from ..types import _custom


class MessageDeleted(EventBuilder, _custom.chatgetter.ChatGetter):
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
    def __init__(self, deleted_ids, peer):
        _custom.chatgetter.ChatGetter.__init__(self, chat_peer=peer)
        self.deleted_id = None if not deleted_ids else deleted_ids[0]
        self.deleted_ids = deleted_ids

    @classmethod
    def _build(cls, update, others=None, self_id=None, *todo, **todo2):
        if isinstance(update, _tl.UpdateDeleteMessages):
            return cls.Event(
                deleted_ids=update.messages,
                peer=None
            )
        elif isinstance(update, _tl.UpdateDeleteChannelMessages):
            return cls.Event(
                deleted_ids=update.messages,
                peer=_tl.PeerChannel(update.channel_id)
            )
