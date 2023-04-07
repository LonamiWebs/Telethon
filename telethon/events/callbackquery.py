import re
import struct

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions
from ..tl.custom.sendergetter import SenderGetter


@name_inner_event
class CallbackQuery(EventBuilder):
    """
    Occurs whenever you sign in as a bot and a user
    clicks one of the inline buttons on your messages.

    Note that the `chats` parameter will **not** work with normal
    IDs or peers if the clicked inline button comes from a "via bot"
    message. The `chats` parameter also supports checking against the
    `chat_instance` which should be used for inline callbacks.

    Args:
        data (`bytes`, `str`, `callable`, optional):
            If set, the inline button payload data must match this data.
            A UTF-8 string can also be given, a regex or a callable. For
            instance, to check against ``'data_1'`` and ``'data_2'`` you
            can use ``re.compile(b'data_')``.

        pattern (`bytes`, `str`, `callable`, `Pattern`, optional):
            If set, only buttons with payload matching this pattern will be handled.
            You can specify a regex-like string which will be matched
            against the payload data, a callable function that returns `True`
            if a the payload data is acceptable, or a compiled regex pattern.

    Example
        .. code-block:: python

            from telethon import events, Button

            # Handle all callback queries and check data inside the handler
            @client.on(events.CallbackQuery)
            async def handler(event):
                if event.data == b'yes':
                    await event.answer('Correct answer!')

            # Handle only callback queries with data being b'no'
            @client.on(events.CallbackQuery(data=b'no'))
            async def handler(event):
                # Pop-up message with alert
                await event.answer('Wrong answer!', alert=True)

            # Send a message with buttons users can click
            async def main():
                await client.send_message(user, 'Yes or no?', buttons=[
                    Button.inline('Yes!', b'yes'),
                    Button.inline('Nope', b'no')
                ])
    """
    def __init__(
            self, chats=None, *, blacklist_chats=False, func=None, data=None, pattern=None):
        super().__init__(chats, blacklist_chats=blacklist_chats, func=func)

        if data and pattern:
            raise ValueError("Only pass either data or pattern not both.")

        if isinstance(data, str):
            data = data.encode('utf-8')
        if isinstance(pattern, str):
            pattern = pattern.encode('utf-8')

        match = data if data else pattern

        if isinstance(match, bytes):
            self.match = data if data else re.compile(pattern).match
        elif not match or callable(match):
            self.match = match
        elif hasattr(match, 'match') and callable(match.match):
            if not isinstance(getattr(match, 'pattern', b''), bytes):
                match = re.compile(match.pattern.encode('utf-8'),
                                   match.flags & (~re.UNICODE))

            self.match = match.match
        else:
            raise TypeError('Invalid data or pattern type given')

        self._no_check = all(x is None for x in (
            self.chats, self.func, self.match,
        ))

    @classmethod
    def build(cls, update, others=None, self_id=None):
        if isinstance(update, types.UpdateBotCallbackQuery):
            return cls.Event(update, update.peer, update.msg_id)
        elif isinstance(update, types.UpdateInlineBotCallbackQuery):
            # See https://github.com/LonamiWebs/Telethon/pull/1005
            # The long message ID is actually just msg_id + peer_id
            mid, pid = struct.unpack('<ii', struct.pack('<q', update.msg_id.id))
            peer = types.PeerChannel(-pid) if pid < 0 else types.PeerUser(pid)
            return cls.Event(update, peer, mid)

    def filter(self, event):
        # We can't call super().filter(...) because it ignores chat_instance
        if self._no_check:
            return event

        if self.chats is not None:
            inside = event.query.chat_instance in self.chats
            if event.chat_id:
                inside |= event.chat_id in self.chats

            if inside == self.blacklist_chats:
                return

        if self.match:
            if callable(self.match):
                event.data_match = event.pattern_match = self.match(event.query.data)
                if not event.data_match:
                    return
            elif event.query.data != self.match:
                return

        if self.func:
            # Return the result of func directly as it may need to be awaited
            return self.func(event)
        return True

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

            pattern_match (`obj`, optional):
                Alias for ``data_match``.
        """
        def __init__(self, query, peer, msg_id):
            super().__init__(peer, msg_id=msg_id)
            SenderGetter.__init__(self, query.user_id)
            self.query = query
            self.data_match = None
            self.pattern_match = None
            self._message = None
            self._answered = False

        def _set_client(self, client):
            super()._set_client(client)
            self._sender, self._input_sender = utils._get_entity_pair(
                self.sender_id, self._entities, client._mb_entity_cache)

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
                    self._input_sender = self._client._mb_entity_cache.get(
                        utils.resolve_id(self._sender_id)[0])._as_input_peer()
                except AttributeError:
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
                    instead of showing a toast. Defaults to `False`.
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

        @property
        def via_inline(self):
            """
            Whether this callback was generated from an inline button sent
            via an inline query or not. If the bot sent the message itself
            with buttons, and one of those is clicked, this will be `False`.
            If a user sent the message coming from an inline query to the
            bot, and one of those is clicked, this will be `True`.

            If it's `True`, it's likely that the bot is **not** in the
            chat, so methods like `respond` or `delete` won't work (but
            `edit` will always work).
            """
            return isinstance(self.query, types.UpdateInlineBotCallbackQuery)

        async def respond(self, *args, **kwargs):
            """
            Responds to the message (not as a reply). Shorthand for
            `telethon.client.messages.MessageMethods.send_message` with
            ``entity`` already set.

            This method also creates a task to `answer` the callback.

            This method will likely fail if `via_inline` is `True`.
            """
            self._client.loop.create_task(self.answer())
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def reply(self, *args, **kwargs):
            """
            Replies to the message (as a reply). Shorthand for
            `telethon.client.messages.MessageMethods.send_message` with
            both ``entity`` and ``reply_to`` already set.

            This method also creates a task to `answer` the callback.

            This method will likely fail if `via_inline` is `True`.
            """
            self._client.loop.create_task(self.answer())
            kwargs['reply_to'] = self.query.msg_id
            return await self._client.send_message(
                await self.get_input_chat(), *args, **kwargs)

        async def edit(self, *args, **kwargs):
            """
            Edits the message. Shorthand for
            `telethon.client.messages.MessageMethods.edit_message` with
            the ``entity`` set to the correct :tl:`InputBotInlineMessageID` or :tl:`InputBotInlineMessageID64`.

            Returns `True` if the edit was successful.

            This method also creates a task to `answer` the callback.

            .. note::

                This method won't respect the previous message unlike
                `Message.edit <telethon.tl.custom.message.Message.edit>`,
                since the message object is normally not present.
            """
            self._client.loop.create_task(self.answer())
            if isinstance(self.query.msg_id, (types.InputBotInlineMessageID, types.InputBotInlineMessageID64)):
                return await self._client.edit_message(
                    self.query.msg_id, *args, **kwargs
                )
            else:
                return await self._client.edit_message(
                    await self.get_input_chat(), self.query.msg_id,
                    *args, **kwargs
                )

        async def delete(self, *args, **kwargs):
            """
            Deletes the message. Shorthand for
            `telethon.client.messages.MessageMethods.delete_messages` with
            ``entity`` and ``message_ids`` already set.

            If you need to delete more than one message at once, don't use
            this `delete` method. Use a
            `telethon.client.telegramclient.TelegramClient` instance directly.

            This method also creates a task to `answer` the callback.

            This method will likely fail if `via_inline` is `True`.
            """
            self._client.loop.create_task(self.answer())
            return await self._client.delete_messages(
                await self.get_input_chat(), [self.query.msg_id],
                *args, **kwargs
            )
