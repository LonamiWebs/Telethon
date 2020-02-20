from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types


@name_inner_event
class MessageRead(EventBuilder):
    """
    Occurs whenever one or more messages are read in a chat.

    Args:
        inbox (`bool`, optional):
            If this argument is `True`, then when you read someone else's
            messages the event will be fired. By default (`False`) only
            when messages you sent are read by someone else will fire it.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.MessageRead)
            async def handler(event):
                # Log when someone reads your messages
                print('Someone has read all your messages until', event.max_id)

            @client.on(events.MessageRead(inbox=True))
            async def handler(event):
                # Log when you read message in a chat (from your "inbox")
                print('You have read messages until', event.max_id)
    """
    def __init__(
            self, chats=None, *, blacklist_chats=False, func=None, inbox=False):
        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)
        self.inbox = inbox

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateReadHistoryInbox):
            return cls.Event(update.peer, update.max_id, False)
        elif isinstance(update, types.UpdateReadHistoryOutbox):
            return cls.Event(update.peer, update.max_id, True)
        elif isinstance(update, types.UpdateReadChannelInbox):
            return cls.Event(types.PeerChannel(update.channel_id),
                             update.max_id, False)
        elif isinstance(update, types.UpdateReadChannelOutbox):
            return cls.Event(types.PeerChannel(update.channel_id),
                             update.max_id, True)
        elif isinstance(update, types.UpdateReadMessagesContents):
            return cls.Event(message_ids=update.messages,
                             contents=True)
        elif isinstance(update, types.UpdateChannelReadMessagesContents):
            return cls.Event(types.PeerChannel(update.channel_id),
                             message_ids=update.messages,
                             contents=True)

    def filter(self, event):
        if self.inbox == event.outbox:
            return

        return super().filter(event)

    class Event(EventCommon):
        """
        Represents the event of one or more messages being read.

        Members:
            max_id (`int`):
                Up to which message ID has been read. Every message
                with an ID equal or lower to it have been read.

            outbox (`bool`):
                `True` if someone else has read your messages.

            contents (`bool`):
                `True` if what was read were the contents of a message.
                This will be the case when e.g. you play a voice note.
                It may only be set on ``inbox`` events.
        """
        def __init__(self, peer=None, max_id=None, out=False, contents=False,
                     message_ids=None):
            self.outbox = out
            self.contents = contents
            self._message_ids = message_ids or []
            self._messages = None
            self.max_id = max_id or max(message_ids or [], default=None)
            super().__init__(peer, self.max_id)

        @property
        def inbox(self):
            """
            `True` if you have read someone else's messages.
            """
            return not self.outbox

        @property
        def message_ids(self):
            """
            The IDs of the messages **which contents'** were read.

            Use :meth:`is_read` if you need to check whether a message
            was read instead checking if it's in here.
            """
            return self._message_ids

        async def get_messages(self):
            """
            Returns the list of `Message <telethon.tl.custom.message.Message>`
            **which contents'** were read.

            Use :meth:`is_read` if you need to check whether a message
            was read instead checking if it's in here.
            """
            if self._messages is None:
                chat = await self.get_input_chat()
                if not chat:
                    self._messages = []
                else:
                    self._messages = await self._client.get_messages(
                        chat, ids=self._message_ids)

            return self._messages

        def is_read(self, message):
            """
            Returns `True` if the given message (or its ID) has been read.

            If a list-like argument is provided, this method will return a
            list of booleans indicating which messages have been read.
            """
            if utils.is_list_like(message):
                return [(m if isinstance(m, int) else m.id) <= self.max_id
                        for m in message]
            else:
                return (message if isinstance(message, int)
                        else message.id) <= self.max_id

        def __contains__(self, message):
            """`True` if the message(s) are read message."""
            if utils.is_list_like(message):
                return all(self.is_read(message))
            else:
                return self.is_read(message)
