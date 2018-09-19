import re
import struct

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions
from ..tl.custom.sendergetter import SenderGetter


@name_inner_event
class CallbackQuery(EventBuilder):
    """
    Represents a callback query event (when an inline button is clicked).

    Note that the `chats` parameter will **not** work with normal
    IDs or peers if the clicked inline button comes from a "via bot"
    message. The `chats` parameter also supports checking against the
    `chat_instance` which should be used for inline callbacks.

    Args:
        data (`bytes` | `str` | `callable`, optional):
            If set, the inline button payload data must match this data.
            A UTF-8 string can also be given, a regex or a callable. For
            instance, to check against ``'data_1'`` and ``'data_2'`` you
            can use ``re.compile(b'data_')``.
    """
    def __init__(
            self, chats=None, *, blacklist_chats=False, func=None, data=None):
        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)

        if isinstance(data, bytes):
            self.data = data
        elif isinstance(data, str):
            self.data = data.encode('utf-8')
        elif not data or callable(data):
            self.data = data
        elif hasattr(data, 'match') and callable(data.match):
            if not isinstance(getattr(data, 'pattern', b''), bytes):
                data = re.compile(data.pattern.encode('utf-8'), data.flags)

            self.data = data.match
        else:
            raise TypeError('Invalid data type given')

    @classmethod
    def build(cls, update):
        if isinstance(update, types.UpdateBotCallbackQuery):
            event = cls.Event(update, update.peer, update.msg_id)
        elif isinstance(update, types.UpdateInlineBotCallbackQuery):
            # See https://github.com/LonamiWebs/Telethon/pull/1005
            # The long message ID is actually just msg_id + peer_id
            mid, pid = struct.unpack('<ii', struct.pack('<q', update.msg_id.id))
            peer = types.PeerChannel(-pid) if pid < 0 else types.PeerUser(pid)
            event = cls.Event(update, peer, mid)
        else:
            return

        event._entities = update._entities
        return event

    def filter(self, event):
        if self.chats is not None:
            inside = event.query.chat_instance in self.chats
            if event.chat_id:
                inside |= event.chat_id in self.chats

            if inside == self.blacklist_chats:
                return None

        if self.data:
            if callable(self.data):
                event.data_match = self.data(event.query.data)
                if not event.data_match:
                    return None
            elif event.query.data != self.data:
                return None

        return event

    class Event(EventCommon, SenderGetter):
        """
        Represents the event of a new callback query.

        Members:
            query (:tl:`UpdateBotCallbackQuery`):
                The original :tl:`UpdateBotCallbackQuery`.

            data_match (`obj`, optional):
                The object returned by the ``data=`` parameter
                when creating the event builder, if any. Similar
                to ``pattern_match`` for the new message event.
        """
        def __init__(self, query, peer, msg_id):
            super().__init__(peer, msg_id=msg_id)
            self.query = query
            self.data_match = None
            self._sender_id = query.user_id
            self._input_sender = None
            self._sender = None
            self._message = None
            self._answered = False

        @property
        def id(self):
            """
            Returns the query ID. The user clicking the inline
            button is the one who generated this random ID.
            """
            return self.query.query_id

        @property
        def message_id(self):
            """
            Returns the message ID to which the clicked inline button belongs.
            """
            return self._message_id

        @property
        def data(self):
            """
            Returns the data payload from the original inline button.
            """
            return self.query.data

        @property
        def chat_instance(self):
            """
            Unique identifier for the chat where the callback occurred.
            Useful for high scores in games.
            """
            return self.query.chat_instance

        async def get_message(self):
            """
            Returns the message to which the clicked inline button belongs.
            """
            if self._message is not None:
                return self._message

            try:
                chat = await self.get_input_chat() if self.is_channel else None
                self._message = await self._client.get_messages(
                    chat, ids=self._message_id)
            except ValueError:
                return

            return self._message

        async def _refetch_sender(self):
            self._sender = self._entities.get(self.sender_id)
            if not self._sender:
                return

            self._input_sender = utils.get_input_peer(self._chat)
            if not getattr(self._input_sender, 'access_hash', True):
                # getattr with True to handle the InputPeerSelf() case
                try:
                    self._input_sender = self._client.session.get_input_entity(
                        self._sender_id
                    )
                except ValueError:
                    m = await self.get_message()
                    if m:
                        self._sender = m._sender
                        self._input_sender = m._input_sender

        async def answer(
                self, message=None, cache_time=0, *, url=None, alert=False):
            """
            Answers the callback query (and stops the loading circle).

            Args:
                message (`str`, optional):
                    The toast message to show feedback to the user.

                cache_time (`int`, optional):
                    For how long this result should be cached on
                    the user's client. Defaults to 0 for no cache.

                url (`str`, optional):
                    The URL to be opened in the user's client. Note that
                    the only valid URLs are those of games your bot has,
                    or alternatively a 't.me/your_bot?start=xyz' parameter.

                alert (`bool`, optional):
                    Whether an alert (a pop-up dialog) should be used
                    instead of showing a toast. Defaults to ``False``.
            """
            if self._answered:
                return

            self._answered = True
            return await self._client(
                functions.messages.SetBotCallbackAnswerRequest(
                    query_id=self.query.query_id,
                    cache_time=cache_time,
                    alert=alert,
                    message=message,
                    url=url
                )
            )

        async def respond(self, *args, **kwargs):
            """
            Responds to the message (not as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            ``entity`` already set.

            This method also creates a task to `answer` the callback.
            """
            self._client.loop.create_task(self.answer())
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def reply(self, *args, **kwargs):
            """
            Replies to the message (as a reply). Shorthand for
            `telethon.telegram_client.TelegramClient.send_message` with
            both ``entity`` and ``reply_to`` already set.

            This method also creates a task to `answer` the callback.
            """
            self._client.loop.create_task(self.answer())
            kwargs['reply_to'] = self.query.msg_id
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def edit(self, *args, **kwargs):
            """
            Edits the message iff it's outgoing. Shorthand for
            `telethon.telegram_client.TelegramClient.edit_message` with
            both ``entity`` and ``message`` already set.

            Returns the edited :tl:`Message`.

            This method also creates a task to `answer` the callback.
            """
            self._client.loop.create_task(self.answer())
            return await self._client.edit_message(
                await self.get_input_chat(), self.query.msg_id,
                *args, **kwargs
            )

        async def delete(self, *args, **kwargs):
            """
            Deletes the message. Shorthand for
            `telethon.telegram_client.TelegramClient.delete_messages` with
            ``entity`` and ``message_ids`` already set.

            If you need to delete more than one message at once, don't use
            this `delete` method. Use a
            `telethon.telegram_client.TelegramClient` instance directly.

            This method also creates a task to `answer` the callback.
            """
            self._client.loop.create_task(self.answer())
            return await self._client.delete_messages(
                await self.get_input_chat(), [self.query.msg_id],
                *args, **kwargs
            )
