import asyncio
import functools
import inspect
import itertools
import time

from .chatgetter import ChatGetter
from ... import helpers, utils, errors

# Sometimes the edits arrive very fast (within the same second).
# In that case we add a small delta so that the age is older, for
# comparision purposes. This value is enough for up to 1000 messages.
_EDIT_COLLISION_DELTA = 0.001


def _checks_cancelled(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if self._cancelled:
            raise asyncio.CancelledError('The conversation was cancelled before')

        return f(self, *args, **kwargs)
    return wrapper


class Conversation(ChatGetter):
    """
    Represents a conversation inside an specific chat.

    A conversation keeps track of new messages since it was
    created until its exit and easily lets you query the
    current state.

    If you need a conversation across two or more chats,
    you should use two conversations and synchronize them
    as you better see fit.
    """
    _id_counter = 0
    _custom_counter = 0

    def __init__(self, client, input_chat,
                 *, timeout, total_timeout, max_messages,
                 exclusive, replies_are_responses):
        # This call resets the client
        ChatGetter.__init__(self, input_chat=input_chat)

        self._id = Conversation._id_counter
        Conversation._id_counter += 1

        self._client = client
        self._timeout = timeout
        self._total_timeout = total_timeout
        self._total_due = None

        self._outgoing = set()
        self._last_outgoing = 0
        self._incoming = []
        self._last_incoming = 0
        self._max_incoming = max_messages
        self._last_read = None
        self._custom = {}

        self._pending_responses = {}
        self._pending_replies = {}
        self._pending_edits = {}
        self._pending_reads = {}

        self._exclusive = exclusive
        self._cancelled = False

        # The user is able to expect two responses for the same message.
        # {desired message ID: next incoming index}
        self._response_indices = {}
        if replies_are_responses:
            self._reply_indices = self._response_indices
        else:
            self._reply_indices = {}

        self._edit_dates = {}

    @_checks_cancelled
    async def send_message(self, *args, **kwargs):
        """
        Sends a message in the context of this conversation. Shorthand
        for `telethon.client.messages.MessageMethods.send_message` with
        ``entity`` already set.
        """
        sent = await self._client.send_message(
            self._input_chat, *args, **kwargs)

        # Albums will be lists, so handle that
        ms = sent if isinstance(sent, list) else (sent,)
        self._outgoing.update(m.id for m in ms)
        self._last_outgoing = ms[-1].id
        return sent

    @_checks_cancelled
    async def send_file(self, *args, **kwargs):
        """
        Sends a file in the context of this conversation. Shorthand
        for `telethon.client.uploads.UploadMethods.send_file` with
        ``entity`` already set.
        """
        sent = await self._client.send_file(
            self._input_chat, *args, **kwargs)

        # Albums will be lists, so handle that
        ms = sent if isinstance(sent, list) else (sent,)
        self._outgoing.update(m.id for m in ms)
        self._last_outgoing = ms[-1].id
        return sent

    @_checks_cancelled
    def mark_read(self, message=None):
        """
        Marks as read the latest received message if ``message is None``.
        Otherwise, marks as read until the given message (or message ID).

        This is equivalent to calling `client.send_read_acknowledge
        <telethon.client.messages.MessageMethods.send_read_acknowledge>`.
        """
        if message is None:
            if self._incoming:
                message = self._incoming[-1].id
            else:
                message = 0
        elif not isinstance(message, int):
            message = message.id

        return self._client.send_read_acknowledge(
            self._input_chat, max_id=message)

    def get_response(self, message=None, *, timeout=None):
        """
        Gets the next message that responds to a previous one. This is
        the method you need most of the time, along with `get_edit`.

        Args:
            message (`Message <telethon.tl.custom.message.Message>` | `int`, optional):
                The message (or the message ID) for which a response
                is expected. By default this is the last sent message.

            timeout (`int` | `float`, optional):
                If present, this `timeout` (in seconds) will override the
                per-action timeout defined for the conversation.

        .. code-block:: python

            async with client.conversation(...) as conv:
                await conv.send_message('Hey, what is your name?')

                response = await conv.get_response()
                name = response.text

                await conv.send_message('Nice to meet you, {}!'.format(name))
        """
        return self._get_message(
            message, self._response_indices, self._pending_responses, timeout,
            lambda x, y: True
        )

    def get_reply(self, message=None, *, timeout=None):
        """
        Gets the next message that explicitly replies to a previous one.
        """
        return self._get_message(
            message, self._reply_indices, self._pending_replies, timeout,
            lambda x, y: x.reply_to and x.reply_to.reply_to_msg_id == y
        )

    def _get_message(
            self, target_message, indices, pending, timeout, condition):
        """
        Gets the next desired message under the desired condition.

        Args:
            target_message (`object`):
                The target message for which we want to find another
                response that applies based on `condition`.

            indices (`dict`):
                This dictionary remembers the last ID chosen for the
                input `target_message`.

            pending (`dict`):
                This dictionary remembers {msg_id: Future} to be set
                once `condition` is met.

            timeout (`int`):
                The timeout (in seconds) override to use for this operation.

            condition (`callable`):
                The condition callable that checks if an incoming
                message is a valid response.
        """
        start_time = time.time()
        target_id = self._get_message_id(target_message)

        # If there is no last-chosen ID, make sure to pick one *after*
        # the input message, since we don't want responses back in time
        if target_id not in indices:
            for i, incoming in enumerate(self._incoming):
                if incoming.id > target_id:
                    indices[target_id] = i
                    break
            else:
                indices[target_id] = len(self._incoming)

        # We will always return a future from here, even if the result
        # can be set immediately. Otherwise, needing to await only
        # sometimes is an annoying edge case (i.e. we would return
        # a `Message` but `get_response()` always `await`'s).
        future = self._client.loop.create_future()

        # If there are enough responses saved return the next one
        last_idx = indices[target_id]
        if last_idx < len(self._incoming):
            incoming = self._incoming[last_idx]
            if condition(incoming, target_id):
                indices[target_id] += 1
                future.set_result(incoming)
                return future

        # Otherwise the next incoming response will be the one to use
        #
        # Note how we fill "pending" before giving control back to the
        # event loop through "await". We want to register it as soon as
        # possible, since any other task switch may arrive with the result.
        pending[target_id] = future
        return self._get_result(future, start_time, timeout, pending, target_id)

    def get_edit(self, message=None, *, timeout=None):
        """
        Awaits for an edit after the last message to arrive.
        The arguments are the same as those for `get_response`.
        """
        start_time = time.time()
        target_id = self._get_message_id(message)

        target_date = self._edit_dates.get(target_id, 0)
        earliest_edit = min(
            (x for x in self._incoming
             if x.edit_date
             and x.id > target_id
             and x.edit_date.timestamp() > target_date
             ),
            key=lambda x: x.edit_date.timestamp(),
            default=None
        )

        future = self._client.loop.create_future()
        if earliest_edit and earliest_edit.edit_date.timestamp() > target_date:
            self._edit_dates[target_id] = earliest_edit.edit_date.timestamp()
            future.set_result(earliest_edit)
            return future  # we should always return something we can await

        # Otherwise the next incoming response will be the one to use
        self._pending_edits[target_id] = future
        return self._get_result(future, start_time, timeout, self._pending_edits, target_id)

    def wait_read(self, message=None, *, timeout=None):
        """
        Awaits for the sent message to be marked as read. Note that
        receiving a response doesn't imply the message was read, and
        this action will also trigger even without a response.
        """
        start_time = time.time()
        future = self._client.loop.create_future()
        target_id = self._get_message_id(message)

        if self._last_read is None:
            self._last_read = target_id - 1

        if self._last_read >= target_id:
            return

        self._pending_reads[target_id] = future
        return self._get_result(future, start_time, timeout, self._pending_reads, target_id)

    async def wait_event(self, event, *, timeout=None):
        """
        Waits for a custom event to occur. Timeouts still apply.

        .. note::

            **Only use this if there isn't another method available!**
            For example, don't use `wait_event` for new messages,
            since `get_response` already exists, etc.

        Unless you're certain that your code will run fast enough,
        generally you should get a "handle" of this special coroutine
        before acting. In this example you will see how to wait for a user
        to join a group with proper use of `wait_event`:

        .. code-block:: python

            from telethon import TelegramClient, events

            client = TelegramClient(...)
            group_id = ...

            async def main():
                # Could also get the user id from an event; this is just an example
                user_id = ...

                async with client.conversation(user_id) as conv:
                    # Get a handle to the future event we'll wait for
                    handle = conv.wait_event(events.ChatAction(
                        group_id,
                        func=lambda e: e.user_joined and e.user_id == user_id
                    ))

                    # Perform whatever action in between
                    await conv.send_message('Please join this group before speaking to me!')

                    # Wait for the event we registered above to fire
                    event = await handle

                    # Continue with the conversation
                    await conv.send_message('Thanks!')

        This way your event can be registered before acting,
        since the response may arrive before your event was
        registered. It depends on your use case since this
        also means the event can arrive before you send
        a previous action.
        """
        start_time = time.time()
        if isinstance(event, type):
            event = event()

        await event.resolve(self._client)

        counter = Conversation._custom_counter
        Conversation._custom_counter += 1

        future = self._client.loop.create_future()
        self._custom[counter] = (event, future)
        try:
            return await self._get_result(future, start_time, timeout, self._custom, counter)
        finally:
            # Need to remove it from the dict if it times out, else we may
            # try and fail to set the result later (#1618).
            self._custom.pop(counter, None)

    async def _check_custom(self, built):
        for key, (ev, fut) in list(self._custom.items()):
            ev_type = type(ev)
            inst = built[ev_type]

            if inst:
                filter = ev.filter(inst)
                if inspect.isawaitable(filter):
                    filter = await filter

                if filter:
                    fut.set_result(inst)
                    del self._custom[key]

    def _on_new_message(self, response):
        response = response.message
        if response.chat_id != self.chat_id or response.out:
            return

        if len(self._incoming) == self._max_incoming:
            self._cancel_all(ValueError('Too many incoming messages'))
            return

        self._incoming.append(response)

        # Most of the time, these dictionaries will contain just one item
        # TODO In fact, why not make it be that way? Force one item only.
        #      How often will people want to wait for two responses at
        #      the same time? It's impossible, first one will arrive
        #      and then another, so they can do that.
        for msg_id, future in list(self._pending_responses.items()):
            self._response_indices[msg_id] = len(self._incoming)
            future.set_result(response)
            del self._pending_responses[msg_id]

        for msg_id, future in list(self._pending_replies.items()):
            if response.reply_to and msg_id == response.reply_to.reply_to_msg_id:
                self._reply_indices[msg_id] = len(self._incoming)
                future.set_result(response)
                del self._pending_replies[msg_id]

    def _on_edit(self, message):
        message = message.message
        if message.chat_id != self.chat_id or message.out:
            return

        # We have to update our incoming messages with the new edit date
        for i, m in enumerate(self._incoming):
            if m.id == message.id:
                self._incoming[i] = message
                break

        for msg_id, future in list(self._pending_edits.items()):
            if msg_id < message.id:
                edit_ts = message.edit_date.timestamp()

                # We compare <= because edit_ts resolution is always to
                # seconds, but we may have increased _edit_dates before.
                # Since the dates are ever growing this is not a problem.
                if edit_ts <= self._edit_dates.get(msg_id, 0):
                    self._edit_dates[msg_id] += _EDIT_COLLISION_DELTA
                else:
                    self._edit_dates[msg_id] = message.edit_date.timestamp()

                future.set_result(message)
                del self._pending_edits[msg_id]

    def _on_read(self, event):
        if event.chat_id != self.chat_id or event.inbox:
            return

        self._last_read = event.max_id

        for msg_id, pending in list(self._pending_reads.items()):
            if msg_id >= self._last_read:
                pending.set_result(True)
                del self._pending_reads[msg_id]

    def _get_message_id(self, message):
        if message is not None:  # 0 is valid but false-y, check for None
            return message if isinstance(message, int) else message.id
        elif self._last_outgoing:
            return self._last_outgoing
        else:
            raise ValueError('No message was sent previously')

    @_checks_cancelled
    def _get_result(self, future, start_time, timeout, pending, target_id):
        due = self._total_due
        if timeout is None:
            timeout = self._timeout

        if timeout is not None:
            due = min(due, start_time + timeout)

        # NOTE: We can't try/finally to pop from pending here because
        #       the event loop needs to get back to us, but it might
        #       dispatch another update before, and in that case a
        #       response could be set twice. So responses must be
        #       cleared when their futures are set to a result.
        return asyncio.wait_for(
            future,
            timeout=None if due == float('inf') else due - time.time()
        )

    def _cancel_all(self, exception=None):
        self._cancelled = True
        for pending in itertools.chain(
                self._pending_responses.values(),
                self._pending_replies.values(),
                self._pending_edits.values()):
            if exception:
                pending.set_exception(exception)
            else:
                pending.cancel()

        for _, fut in self._custom.values():
            if exception:
                fut.set_exception(exception)
            else:
                fut.cancel()

    async def __aenter__(self):
        self._input_chat = \
            await self._client.get_input_entity(self._input_chat)

        self._chat_peer = utils.get_peer(self._input_chat)

        # Make sure we're the only conversation in this chat if it's exclusive
        chat_id = utils.get_peer_id(self._chat_peer)
        conv_set = self._client._conversations[chat_id]
        if self._exclusive and conv_set:
            raise errors.AlreadyInConversationError()

        conv_set.add(self)
        self._cancelled = False

        self._last_outgoing = 0
        self._last_incoming = 0
        for d in (
                self._outgoing, self._incoming,
                self._pending_responses, self._pending_replies,
                self._pending_edits, self._response_indices,
                self._reply_indices, self._edit_dates, self._custom):
            d.clear()

        if self._total_timeout:
            self._total_due = time.time() + self._total_timeout
        else:
            self._total_due = float('inf')

        return self

    def cancel(self):
        """
        Cancels the current conversation. Pending responses and subsequent
        calls to get a response will raise ``asyncio.CancelledError``.

        This method is synchronous and should not be awaited.
        """
        self._cancel_all()

    async def cancel_all(self):
        """
        Calls `cancel` on *all* conversations in this chat.

        Note that you should ``await`` this method, since it's meant to be
        used outside of a context manager, and it needs to resolve the chat.
        """
        chat_id = await self._client.get_peer_id(self._input_chat)
        for conv in self._client._conversations[chat_id]:
            conv.cancel()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        chat_id = utils.get_peer_id(self._chat_peer)
        conv_set = self._client._conversations[chat_id]
        conv_set.discard(self)
        if not conv_set:
            del self._client._conversations[chat_id]

        self._cancel_all()

    __enter__ = helpers._sync_enter
    __exit__ = helpers._sync_exit
