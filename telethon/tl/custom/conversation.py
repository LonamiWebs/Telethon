import asyncio
import itertools
import time

from .chatgetter import ChatGetter
from ... import utils


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
                 replies_are_responses):
        self._id = Conversation._id_counter
        Conversation._id_counter += 1

        self._client = client
        self._chat = None
        self._input_chat = input_chat
        self._chat_peer = None
        self._broadcast = None

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

        # The user is able to expect two responses for the same message.
        # {desired message ID: next incoming index}
        self._response_indices = {}
        if replies_are_responses:
            self._reply_indices = self._response_indices
        else:
            self._reply_indices = {}

        self._edit_dates = {}

    async def send_message(self, *args, **kwargs):
        """
        Sends a message in the context of this conversation. Shorthand
        for `telethon.client.messages.MessageMethods.send_message` with
        ``entity`` already set.
        """
        message = await self._client.send_message(
            self._input_chat, *args, **kwargs)

        self._outgoing.add(message.id)
        self._last_outgoing = message.id
        return message

    async def send_file(self, *args, **kwargs):
        """
        Sends a file in the context of this conversation. Shorthand
        for `telethon.client.uploads.UploadMethods.send_file` with
        ``entity`` already set.
        """
        message = await self._client.send_file(
            self._input_chat, *args, **kwargs)

        self._outgoing.add(message.id)
        self._last_outgoing = message.id
        return message

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

    async def get_response(self, message=None, *, timeout=None):
        """
        Returns a coroutine that will resolve once a response arrives.

        Args:
            message (:tl:`Message` | `int`, optional):
                The message (or the message ID) for which a response
                is expected. By default this is the last sent message.

            timeout (`int` | `float`, optional):
                If present, this `timeout` will override the
                per-action timeout defined for the conversation.
        """
        return await self._get_message(
            message, self._response_indices, self._pending_responses, timeout,
            lambda x, y: True
        )

    async def get_reply(self, message=None, *, timeout=None):
        """
        Returns a coroutine that will resolve once a reply
        (that is, a message being a reply) arrives. The
        arguments are the same as those for `get_response`.
        """
        return await self._get_message(
            message, self._reply_indices, self._pending_replies, timeout,
            lambda x, y: x.reply_to_msg_id == y
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
                The timeout override to use for this operation.

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

        # If there are enough responses saved return the next one
        last_idx = indices[target_id]
        if last_idx < len(self._incoming):
            incoming = self._incoming[last_idx]
            if condition(incoming, target_id):
                indices[target_id] += 1
                return incoming

        # Otherwise the next incoming response will be the one to use
        future = self._client.loop.create_future()
        pending[target_id] = future
        return self._get_result(future, start_time, timeout)

    async def get_edit(self, message=None, *, timeout=None):
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

        if earliest_edit and earliest_edit.edit_date.timestamp() > target_date:
            self._edit_dates[target_id] = earliest_edit.edit_date.timestamp()
            return earliest_edit

        # Otherwise the next incoming response will be the one to use
        future = asyncio.Future(loop=self._client.loop)
        self._pending_edits[target_id] = future
        return await self._get_result(future, start_time, timeout)

    async def wait_read(self, message=None, *, timeout=None):
        """
        Awaits for the sent message to be read. Note that receiving
        a response doesn't imply the message was read, and this action
        will also trigger even without a response.
        """
        start_time = time.time()
        future = self._client.loop.create_future()
        target_id = self._get_message_id(message)

        if self._last_read is None:
            self._last_read = target_id - 1

        if self._last_read >= target_id:
            return

        self._pending_reads[target_id] = future
        return await self._get_result(future, start_time, timeout)

    async def wait_event(self, event, *, timeout=None):
        """
        Waits for a custom event to occur. Timeouts still apply.

        Unless you're certain that your code will run fast enough,
        generally you should get a "handle" of this special coroutine
        before acting. Generally, you should do this:

        >>> from telethon import TelegramClient, events
        >>>
        >>> client = TelegramClient(...)
        >>>
        >>> async def main():
        >>>     async with client.conversation(...) as conv:
        >>>         response = conv.wait_event(events.NewMessage(incoming=True))
        >>>         await conv.send_message('Hi')
        >>>         response = await response

        This way your event can be registered before acting,
        since the response may arrive before your event was
        registered. It depends on your use case since this
        also means the event can arrive before you send
        a previous action.
        """
        start_time = time.time()
        if isinstance(event, type):
            event = event()

        # Since we await resolve here we don't need to await resolved.
        # We know it has already been resolved, unlike when normally
        # adding an event handler, for which a task is created to resolve.
        await event.resolve()

        counter = Conversation._custom_counter
        Conversation._custom_counter += 1

        future = asyncio.Future(loop=self._client.loop)
        async def result():
            try:
                return await self._get_result(future, start_time, timeout)
            finally:
                del self._custom[counter]

        self._custom[counter] = (event, future)
        return await result()

    async def _check_custom(self, built):
        for i, (ev, fut) in self._custom.items():
            ev_type = type(ev)
            if built[ev_type] and ev.filter(built[ev_type]):
                fut.set_result(built[ev_type])

    def _on_new_message(self, response):
        response = response.message
        if response.chat_id != self.chat_id or response.out:
            return

        if len(self._incoming) == self._max_incoming:
            self._cancel_all(ValueError('Too many incoming messages'))
            return

        self._incoming.append(response)

        found = []
        for msg_id in self._pending_responses:
            found.append(msg_id)
            self._response_indices[msg_id] = len(self._incoming)

        for msg_id in found:
            self._pending_responses.pop(msg_id).set_result(response)

        found.clear()
        for msg_id in self._pending_replies:
            if msg_id == response.reply_to_msg_id:
                found.append(msg_id)
                self._reply_indices[msg_id] = len(self._incoming)

        for msg_id in found:
            self._pending_replies.pop(msg_id).set_result(response)

    def _on_edit(self, message):
        message = message.message
        if message.chat_id != self.chat_id or message.out:
            return

        found = []
        for msg_id, pending in self._pending_edits.items():
            if msg_id < message.id:
                found.append(msg_id)
                self._edit_dates[msg_id] = message.edit_date.timestamp()

        for msg_id in found:
            self._pending_edits.pop(msg_id).set_result(message)

    def _on_read(self, event):
        if event.chat_id != self.chat_id or event.inbox:
            return

        self._last_read = event.max_id

        remove_reads = []
        for msg_id, pending in self._pending_reads.items():
            if msg_id >= self._last_read:
                remove_reads.append(msg_id)
                pending.set_result(True)

        for to_remove in remove_reads:
            del self._pending_reads[to_remove]

    def _get_message_id(self, message):
        if message:
            return message if isinstance(message, int) else message.id
        elif self._last_outgoing:
            return self._last_outgoing
        else:
            raise ValueError('No message was sent previously')

    def _get_result(self, future, start_time, timeout):
        due = self._total_due
        if timeout is None:
            timeout = self._timeout

        if timeout is not None:
            due = min(due, start_time + timeout)

        return asyncio.wait_for(
            future,
            timeout=None if due == float('inf') else due - time.time(),
            loop=self._client.loop
        )

    def _cancel_all(self, exception=None):
        for pending in itertools.chain(
                self._pending_responses.values(),
                self._pending_replies.values(),
                self._pending_edits.values()):
            if exception:
                pending.set_exception(exception)
            else:
                pending.cancel()

        for _, fut, _ in self._custom:
            if exception:
                fut.set_exception(exception)
            else:
                fut.cancel()

    def __enter__(self):
        return self._client.loop.run_until_complete(self.__aenter__())

    async def __aenter__(self):
        self._client._conversations[self._id] = self
        self._input_chat = \
            await self._client.get_input_entity(self._input_chat)

        self._chat_peer = utils.get_peer(self._input_chat)
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

    def __exit__(self, *args):
        return self._client.loop.run_until_complete(self.__aexit__(*args))

    async def __aexit__(self, *args):
        del self._client._conversations[self._id]
        self._cancel_all()
