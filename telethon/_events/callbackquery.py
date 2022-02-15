import re
import struct
import asyncio
import functools

from .base import EventBuilder
from .._misc import utils
from .. import _tl
from ..types import _custom


def auto_answer(func):
    @functools.wraps(func)
    async def wrapped(self, *args, **kwargs):
        if self._answered:
            return await func(*args, **kwargs)
        else:
            return (await asyncio.gather(
                self._answer(),
                func(*args, **kwargs),
            ))[1]

    return wrapped


class CallbackQuery(EventBuilder, _custom.chatgetter.ChatGetter, _custom.sendergetter.SenderGetter):
    """
    Occurs whenever you sign in as a bot and a user
    clicks one of the inline buttons on your messages.

    Note that the `chats` parameter will **not** work with normal
    IDs or peers if the clicked inline button comes from a "via bot"
    message. The `chats` parameter also supports checking against the
    `chat_instance` which should be used for inline callbacks.

    Members:
        query (:tl:`UpdateBotCallbackQuery`):
            The original :tl:`UpdateBotCallbackQuery`.

        data_match (`obj`, optional):
            The object returned by the ``data=`` parameter
            when creating the event builder, if any. Similar
            to ``pattern_match`` for the new message event.

        pattern_match (`obj`, optional):
            Alias for ``data_match``.

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
    @classmethod
    def _build(cls, client, update, entities):
        query = update
        if isinstance(update, _tl.UpdateBotCallbackQuery):
            peer = update.peer
            msg_id = update.msg_id
        elif isinstance(update, _tl.UpdateInlineBotCallbackQuery):
            # See https://github.com/LonamiWebs/Telethon/pull/1005
            # The long message ID is actually just msg_id + peer_id
            msg_id, pid = struct.unpack('<ii', struct.pack('<q', update.msg_id.id))
            peer = _tl.PeerChannel(-pid) if pid < 0 else _tl.PeerUser(pid)
        else:
            return None

        self = cls.__new__(cls)
        self._client = client
        self._sender = entities.get(_tl.PeerUser(query.user_id))
        self._chat = entities.get(peer)

        self.query = query
        self.data_match = None
        self.pattern_match = None
        self._message = None
        self._answered = False

        return self

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
            self._message = await self._client.get_messages(self.chat, ids=self._message_id)
        except ValueError:
            return

        return self._message

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

        res = await self._client(_tl.fn.messages.SetBotCallbackAnswer(
            query_id=self.query.query_id,
            cache_time=cache_time,
            alert=alert,
            message=message,
            url=url,
        ))
        self._answered = True
        return res

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
        return isinstance(self.query, _tl.UpdateInlineBotCallbackQuery)

    @auto_answer
    async def respond(self, *args, **kwargs):
        """
        Responds to the message (not as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message` with
        ``entity`` already set.

        This method will also `answer` the callback if necessary.

        This method will likely fail if `via_inline` is `True`.
        """
        return await self._client.send_message(
            await self.get_input_chat(), *args, **kwargs)

    @auto_answer
    async def reply(self, *args, **kwargs):
        """
        Replies to the message (as a reply). Shorthand for
        `telethon.client.messages.MessageMethods.send_message` with
        both ``entity`` and ``reply_to`` already set.

        This method will also `answer` the callback if necessary.

        This method will likely fail if `via_inline` is `True`.
        """
        kwargs['reply_to'] = self.query.msg_id
        return await self._client.send_message(
            await self.get_input_chat(), *args, **kwargs)

    @auto_answer
    async def edit(self, *args, **kwargs):
        """
        Edits the message. Shorthand for
        `telethon.client.messages.MessageMethods.edit_message` with
        the ``entity`` set to the correct :tl:`InputBotInlineMessageID`.

        Returns `True` if the edit was successful.

        This method will also `answer` the callback if necessary.

        .. note::

            This method won't respect the previous message unlike
            `Message.edit <telethon.tl._custom.message.Message.edit>`,
            since the message object is normally not present.
        """
        if isinstance(self.query.msg_id, _tl.InputBotInlineMessageID):
            return await self._client.edit_message(
                None, self.query.msg_id, *args, **kwargs
            )
        else:
            return await self._client.edit_message(
                await self.get_input_chat(), self.query.msg_id,
                *args, **kwargs
            )

    @auto_answer
    async def delete(self, *args, **kwargs):
        """
        Deletes the message. Shorthand for
        `telethon.client.messages.MessageMethods.delete_messages` with
        ``entity`` and ``message_ids`` already set.

        If you need to delete more than one message at once, don't use
        this `delete` method. Use a
        `telethon.client.telegramclient.TelegramClient` instance directly.

        This method will also `answer` the callback if necessary.

        This method will likely fail if `via_inline` is `True`.
        """
        return await self._client.delete_messages(
            await self.get_input_chat(), [self.query.msg_id],
            *args, **kwargs
        )
