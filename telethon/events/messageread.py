from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions


@name_inner_event
class MessageRead(EventBuilder):
    """
    Event fired when one or more messages have been read.

    Args:
        inbox (`bool`, optional):
            If this argument is ``True``, then when you read someone else's
            messages the event will be fired. By default (``False``) only
            when messages you sent are read by someone else will fire it.
    """
    def __init__(self, inbox=False, chats=None, blacklist_chats=None):
        super().__init__(chats, blacklist_chats)
        self.inbox = inbox

    def build(self, update):
        if isinstance(update, types.UpdateReadHistoryInbox):
            event = MessageRead.Event(update.peer, update.max_id, False)
        elif isinstance(update, types.UpdateReadHistoryOutbox):
            event = MessageRead.Event(update.peer, update.max_id, True)
        elif isinstance(update, types.UpdateReadChannelInbox):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      update.max_id, False)
        elif isinstance(update, types.UpdateReadChannelOutbox):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      update.max_id, True)
        elif isinstance(update, types.UpdateReadMessagesContents):
            event = MessageRead.Event(message_ids=update.messages,
                                      contents=True)
        elif isinstance(update, types.UpdateChannelReadMessagesContents):
            event = MessageRead.Event(types.PeerChannel(update.channel_id),
                                      message_ids=update.messages,
                                      contents=True)
        else:
            return

        if self.inbox == event.outbox:
            return

        event._entities = update._entities
        return self._filter_event(event)

    class Event(EventCommon):
        """
        Represents the event of one or more messages being read.

        Members:
            max_id (`int`):
                Up to which message ID has been read. Every message
                with an ID equal or lower to it have been read.

            outbox (`bool`):
                ``True`` if someone else has read your messages.

            contents (`bool`):
                ``True`` if what was read were the contents of a message.
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
            ``True`` if you have read someone else's messages.
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

        @property
        def messages(self):
            """
            The list of `telethon.tl.custom.message.Message`
            **which contents'** were read.

            Use :meth:`is_read` if you need to check whether a message
            was read instead checking if it's in here.
            """
            if self._messages is None:
                chat = self.input_chat
                if not chat:
                    self._messages = []
                else:
                    self._messages = self._client.get_messages(
                        chat, ids=self._message_ids)

            return self._messages

        def is_read(self, message):
            """
            Returns ``True`` if the given message (or its ID) has been read.

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
            """``True`` if the message(s) are read message."""
            if utils.is_list_like(message):
                return all(self.is_read(message))
            else:
                return self.is_read(message)
