from .base import EventBuilder
from .._misc import utils
from .. import _tl


class MessageRead(EventBuilder):
    """
    Occurs whenever one or more messages are read in a chat.

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
    def __init__(self, peer=None, max_id=None, out=False, contents=False,
                    message_ids=None):
        self.outbox = out
        self.contents = contents
        self._message_ids = message_ids or []
        self._messages = None
        self.max_id = max_id or max(message_ids or [], default=None)
        super().__init__(peer, self.max_id)

    @classmethod
    def _build(cls, client, update, entities):
        out = False
        contents = False
        message_ids = None
        if isinstance(update, _tl.UpdateReadHistoryInbox):
            peer = update.peer
            max_id = update.max_id
            out = False
        elif isinstance(update, _tl.UpdateReadHistoryOutbox):
            peer = update.peer
            max_id = update.max_id
            out = True
        elif isinstance(update, _tl.UpdateReadChannelInbox):
            peer = _tl.PeerChannel(update.channel_id)
            max_id = update.max_id
            out = False
        elif isinstance(update, _tl.UpdateReadChannelOutbox):
            peer = _tl.PeerChannel(update.channel_id)
            max_id = update.max_id
            out = True
        elif isinstance(update, _tl.UpdateReadMessagesContents):
            peer = None
            message_ids = update.messages
            contents = True
        elif isinstance(update, _tl.UpdateChannelReadMessagesContents):
            peer = _tl.PeerChannel(update.channel_id)
            message_ids = update.messages
            contents = True

        self = cls.__new__(cls)
        self._client = client
        self._chat = entities.get(peer)
        return self

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
