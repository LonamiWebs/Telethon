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
        if total_timeout:
            self._total_due = time.time() + total_timeout
        else:
            self._total_due = float('inf')

        self._outgoing = set()
        self._last_outgoing = 0
        self._incoming = []
        self._last_incoming = 0
        self._max_incoming = max_messages
        self._last_read = None

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

        self._edit_indices = {}

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

    async def get_response(self, message=None, *, timeout=None):
        """
        Awaits for a response to arrive.

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
        Awaits for a reply (that is, a message being a reply) to arrive.
        The arguments are the same as those for `get_response`.
        """
        return await self._get_message(
            message, self._reply_indices, self._pending_replies, timeout,
            lambda x, y: x.reply_to_msg_id == y
        )

    async def get_edit(self, message=None, *, timeout=None):
        """
        Awaits for an edit after the last message to arrive.
        The arguments are the same as those for `get_response`.
        """
        return await self._get_message(
            message, self._reply_indices, self._pending_edits, timeout,
            lambda x, y: x.edit_date
        )

    async def _get_message(
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
        now = time.time()
        future = asyncio.Future()
        target_id = self._get_message_id(target_message)

        # If there is no last-chosen ID, make sure to pick one *after*
        # the input message, since we don't want responses back in time
        if target_id not in indices:
            for i, incoming in self._incoming:
                if incoming.id > target_id:
                    indices[target_id] = i
                    break
            else:
                indices[target_id] = 0

        # If there are enough responses saved return the next one
        last_idx = indices[target_id]
        if last_idx < len(self._incoming):
            incoming = self._incoming[last_idx]
            if condition(incoming, target_id):
                indices[target_id] += 1
                return incoming

        # Otherwise the next incoming response will be the one to use
        pending[target_id] = future
        done, pending = await asyncio.wait(
            [future, self._sleep(now, timeout)],
            return_when=asyncio.FIRST_COMPLETED
        )
        if future in pending:
            for future in pending:
                future.cancel()

            raise asyncio.TimeoutError()
        else:
            return future.result()

    async def wait_read(self, message=None, *, timeout=None):
        """
        Awaits for the sent message to be read. Note that receiving
        a response doesn't imply the message was read, and this action
        will also trigger even without a response.
        """
        now = time.time()
        future = asyncio.Future()
        target_id = self._get_message_id(message)

        if self._last_read is None:
            self._last_read = target_id - 1

        if self._last_read >= target_id:
            return

        self._pending_reads[target_id] = future
        done, pending = await asyncio.wait(
            [future, self._sleep(now, timeout)],
            return_when=asyncio.FIRST_COMPLETED
        )
        if future in pending:
            for future in pending:
                future.cancel()

            raise asyncio.TimeoutError()
        else:
            return future.result()

    def _on_new_message(self, response):
        if response.chat_id != self.chat_id or response.out:
            return

        if len(self._incoming) == self._max_incoming:
            too_many = ValueError('Too many incoming messages')
            for pending in itertools.chain(
                    self._pending_responses.values(),
                    self._pending_replies.values(),
                    self._pending_edits):
                pending.set_exception(too_many)
            return

        self._incoming.append(response)
        for msg_id, pending in self._pending_responses.items():
            self._response_indices[msg_id] = len(self._incoming)
            pending.set_result(response)

        self._pending_responses.clear()

        remove_replies = []
        for msg_id, pending in self._pending_replies.items():
            if msg_id == response.reply_to_msg_id:
                remove_replies.append(msg_id)
                self._reply_indices[msg_id] = len(self._incoming)
                pending.set_result(response)

        for to_remove in remove_replies:
            del self._reply_indices[to_remove]

    # TODO Edits are different since they work by date not indices
    # That is, we need to scan all incoming messages and detect if
    # the last used edit date is different from the one we knew.
    def _on_edit(self, message):
        if message.chat_id != self.chat_id or message.out:
            return

        for i, msg in enumerate(self._incoming):
            if msg.id == message.id:
                self._incoming[i] = msg
                break

        remove_edits = []
        for msg_id, pending in self._pending_replies.items():
            if msg_id == message.id:
                remove_edits.append(msg_id)
                self._edit_indices[msg_id] = len(self._incoming)
                pending.set_result(message)

        for to_remove in remove_edits:
            del self._edit_indices[to_remove]

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

    async def _sleep(self, now, timeout):
        due = self._total_due
        if timeout is None:
            timeout = self._timeout

        if timeout is not None:
            due = min(due, now + timeout)

        try:
            if due == float('inf'):
                while True:
                    await asyncio.sleep(60)
            elif due > now:
                await asyncio.sleep(due - now)
        except asyncio.CancelledError:
            pass

    async def __aenter__(self):
        self._client._conversations[self._id] = self
        self._input_chat = \
            await self._client.get_input_entity(self._input_chat)

        self._chat_peer = utils.get_peer(self._input_chat)
        self._outgoing.clear()
        self._last_outgoing = 0
        self._incoming.clear()
        self._last_incoming = 0
        self._pending_responses.clear()
        self._response_indices.clear()
        return self

    async def __aexit__(self, *args):
        del self._client._conversations[self._id]
