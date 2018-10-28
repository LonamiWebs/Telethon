import asyncio
import collections
import functools
import logging

from . import authenticator
from ..extensions.messagepacker import MessagePacker
from .mtprotoplainsender import MTProtoPlainSender
from .requeststate import RequestState
from .mtprotostate import MTProtoState
from ..tl.tlobject import TLRequest
from .. import utils
from ..errors import (
    BadMessageError, InvalidBufferError, SecurityError,
    TypeNotFoundError, rpc_message_to_error
)
from ..extensions import BinaryReader
from ..tl.core import RpcResult, MessageContainer, GzipPacked
from ..tl.functions.auth import LogOutRequest
from ..tl.types import (
    MsgsAck, Pong, BadServerSalt, BadMsgNotification, FutureSalts,
    MsgNewDetailedInfo, NewSessionCreated, MsgDetailedInfo, MsgsStateReq,
    MsgsStateInfo, MsgsAllInfo, MsgResendReq, upload
)
from ..crypto import AuthKey

__log__ = logging.getLogger(__name__)


def _cancellable(func):
    """
    Silences `asyncio.CancelledError` for an entire function.

    This way the function can be cancelled without the task ending
    with a exception, and without the function body requiring another
    indent level for the try/except.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except asyncio.CancelledError:
            pass
    return wrapped


class MTProtoSender:
    """
    MTProto Mobile Protocol sender
    (https://core.telegram.org/mtproto/description).

    This class is responsible for wrapping requests into `TLMessage`'s,
    sending them over the network and receiving them in a safe manner.

    Automatic reconnection due to temporary network issues is a concern
    for this class as well, including retry of messages that could not
    be sent successfully.

    A new authorization key will be generated on connection if no other
    key exists yet.
    """
    def __init__(self, auth_key, loop, *,
                 retries=5, delay=1, auto_reconnect=True, connect_timeout=None,
                 update_callback=None, auto_reconnect_callback=None):
        self._connection = None
        self._loop = loop
        self._retries = retries
        self._delay = delay
        self._auto_reconnect = auto_reconnect
        self._connect_timeout = connect_timeout
        self._update_callback = update_callback
        self._auto_reconnect_callback = auto_reconnect_callback

        # Whether the user has explicitly connected or disconnected.
        #
        # If a disconnection happens for any other reason and it
        # was *not* user action then the pending messages won't
        # be cleared but on explicit user disconnection all the
        # pending futures should be cancelled.
        self._user_connected = False
        self._reconnecting = False
        self._disconnected = self._loop.create_future()
        self._disconnected.set_result(None)

        # We need to join the loops upon disconnection
        self._send_loop_handle = None
        self._recv_loop_handle = None

        # Preserving the references of the AuthKey and state is important
        self.auth_key = auth_key or AuthKey(None)
        self._state = MTProtoState(self.auth_key)

        # Outgoing messages are put in a queue and sent in a batch.
        # Note that here we're also storing their ``_RequestState``.
        self._send_queue = MessagePacker(self._state, self._loop)

        # Sent states are remembered until a response is received.
        self._pending_state = {}

        # Responses must be acknowledged, and we can also batch these.
        self._pending_ack = set()

        # Similar to pending_messages but only for the last acknowledges.
        # These can't go in pending_messages because no acknowledge for them
        # is received, but we may still need to resend their state on bad salts.
        self._last_acks = collections.deque(maxlen=10)

        # Jump table from response ID to method that handles it
        self._handlers = {
            RpcResult.CONSTRUCTOR_ID: self._handle_rpc_result,
            MessageContainer.CONSTRUCTOR_ID: self._handle_container,
            GzipPacked.CONSTRUCTOR_ID: self._handle_gzip_packed,
            Pong.CONSTRUCTOR_ID: self._handle_pong,
            BadServerSalt.CONSTRUCTOR_ID: self._handle_bad_server_salt,
            BadMsgNotification.CONSTRUCTOR_ID: self._handle_bad_notification,
            MsgDetailedInfo.CONSTRUCTOR_ID: self._handle_detailed_info,
            MsgNewDetailedInfo.CONSTRUCTOR_ID: self._handle_new_detailed_info,
            NewSessionCreated.CONSTRUCTOR_ID: self._handle_new_session_created,
            MsgsAck.CONSTRUCTOR_ID: self._handle_ack,
            FutureSalts.CONSTRUCTOR_ID: self._handle_future_salts,
            MsgsStateReq.CONSTRUCTOR_ID: self._handle_state_forgotten,
            MsgResendReq.CONSTRUCTOR_ID: self._handle_state_forgotten,
            MsgsAllInfo.CONSTRUCTOR_ID: self._handle_msg_all,
        }

    # Public API

    async def connect(self, connection):
        """
        Connects to the specified given connection using the given auth key.
        """
        if self._user_connected:
            __log__.info('User is already connected!')
            return

        self._connection = connection
        self._user_connected = True
        await self._connect()

    def is_connected(self):
        return self._user_connected

    def disconnect(self):
        """
        Cleanly disconnects the instance from the network, cancels
        all pending requests, and closes the send and receive loops.
        """
        self._disconnect()

    def send(self, request, ordered=False):
        """
        This method enqueues the given request to be sent. Its send
        state will be saved until a response arrives, and a ``Future``
        that will be resolved when the response arrives will be returned:

        .. code-block:: python

            async def method():
                # Sending (enqueued for the send loop)
                future = sender.send(request)
                # Receiving (waits for the receive loop to read the result)
                result = await future

        Designed like this because Telegram may send the response at
        any point, and it can send other items while one waits for it.
        Once the response for this future arrives, it is set with the
        received result, quite similar to how a ``receive()`` call
        would otherwise work.

        Since the receiving part is "built in" the future, it's
        impossible to await receive a result that was never sent.
        """
        if not self._user_connected:
            raise ConnectionError('Cannot send requests while disconnected')

        if not utils.is_list_like(request):
            state = RequestState(request, self._loop)
            self._send_queue.append(state)
            return state.future
        else:
            states = []
            futures = []
            state = None
            for req in request:
                state = RequestState(req, self._loop, after=ordered and state)
                states.append(state)
                futures.append(state.future)

            self._send_queue.extend(states)
            return futures

    @property
    def disconnected(self):
        """
        Future that resolves when the connection to Telegram
        ends, either by user action or in the background.

        Note that it may resolve in either a ``ConnectionError``
        or any other unexpected error that could not be handled.
        """
        return asyncio.shield(self._disconnected, loop=self._loop)

    # Private methods

    async def _connect(self):
        """
        Performs the actual connection, retrying, generating the
        authorization key if necessary, and starting the send and
        receive loops.
        """
        __log__.info('Connecting to %s...', self._connection)
        for retry in range(1, self._retries + 1):
            try:
                __log__.debug('Connection attempt {}...'.format(retry))
                await self._connection.connect(timeout=self._connect_timeout)
            except (ConnectionError, asyncio.TimeoutError) as e:
                __log__.warning('Attempt {} at connecting failed: {}: {}'
                                .format(retry, type(e).__name__, e))
                await asyncio.sleep(self._delay)
            else:
                break
        else:
            raise ConnectionError('Connection to Telegram failed {} times'
                                  .format(self._retries))

        __log__.debug('Connection success!')
        if not self.auth_key:
            plain = MTProtoPlainSender(self._connection)
            for retry in range(1, self._retries + 1):
                try:
                    __log__.debug('New auth_key attempt {}...'.format(retry))
                    self.auth_key.key, self._state.time_offset =\
                        await authenticator.do_authentication(plain)

                    break
                except (SecurityError, AssertionError) as e:
                    __log__.warning('Attempt {} at new auth_key failed: {}'
                                    .format(retry, e))
                    await asyncio.sleep(self._delay)
            else:
                e = ConnectionError('auth_key generation failed {} times'
                                    .format(self._retries))
                self._disconnect(error=e)
                raise e

        __log__.debug('Starting send loop')
        self._send_loop_handle = self._loop.create_task(self._send_loop())

        __log__.debug('Starting receive loop')
        self._recv_loop_handle = self._loop.create_task(self._recv_loop())

        # _disconnected only completes after manual disconnection
        # or errors after which the sender cannot continue such
        # as failing to reconnect or any unexpected error.
        if self._disconnected.done():
            self._disconnected = self._loop.create_future()

        __log__.info('Connection to %s complete!', self._connection)

    def _disconnect(self, error=None):
        __log__.info('Disconnecting from %s...', self._connection)
        self._user_connected = False
        try:
            __log__.debug('Closing current connection...')
            self._connection.disconnect()
        finally:
            __log__.debug('Cancelling {} pending message(s)...'
                          .format(len(self._pending_state)))
            for state in self._pending_state.values():
                if error and not state.future.done():
                    state.future.set_exception(error)
                else:
                    state.future.cancel()

            self._pending_state.clear()
            self._pending_ack.clear()
            self._last_ack = None

            if self._send_loop_handle:
                __log__.debug('Cancelling the send loop...')
                self._send_loop_handle.cancel()

            if self._recv_loop_handle:
                __log__.debug('Cancelling the receive loop...')
                self._recv_loop_handle.cancel()

        __log__.info('Disconnection from %s complete!', self._connection)
        if self._disconnected and not self._disconnected.done():
            if error:
                self._disconnected.set_exception(error)
            else:
                self._disconnected.set_result(None)

    async def _reconnect(self):
        """
        Cleanly disconnects and then reconnects.
        """
        self._reconnecting = True

        __log__.debug('Closing current connection...')
        self._connection.disconnect()

        __log__.debug('Cancelling the send loop...')
        self._send_loop_handle.cancel()

        __log__.debug('Cancelling the receive loop...')
        self._recv_loop_handle.cancel()

        self._reconnecting = False

        # Start with a clean state (and thus session ID) to avoid old msgs
        self._state.reset()

        retries = self._retries if self._auto_reconnect else 0
        for retry in range(1, retries + 1):
            try:
                await self._connect()
            except ConnectionError:
                __log__.info('Failed reconnection retry %d/%d', retry, retries)
                await asyncio.sleep(self._delay)
            else:
                self._send_queue.extend(self._pending_state.values())
                self._pending_state.clear()

                if self._auto_reconnect_callback:
                    self._loop.create_task(self._auto_reconnect_callback())

                break
        else:
            __log__.error('Failed to reconnect automatically.')
            self._disconnect(error=ConnectionError())

    def _start_reconnect(self):
        """Starts a reconnection in the background."""
        if self._user_connected:
            self._loop.create_task(self._reconnect())

    # Loops

    @_cancellable
    async def _send_loop(self):
        """
        This loop is responsible for popping items off the send
        queue, encrypting them, and sending them over the network.

        Besides `connect`, only this method ever sends data.
        """
        while self._user_connected and not self._reconnecting:
            if self._pending_ack:
                ack = RequestState(MsgsAck(list(self._pending_ack)), self._loop)
                self._send_queue.append(ack)
                self._last_acks.append(ack)
                self._pending_ack.clear()

            __log__.debug('Waiting for messages to send...')
            # TODO Wait for the connection send queue to be empty?
            # This means that while it's not empty we can wait for
            # more messages to be added to the send queue.
            batch, data = await self._send_queue.get()

            if not data:
                continue

            __log__.debug('Encrypting %d message(s) in %d bytes for sending',
                          len(batch), len(data))

            data = self._state.encrypt_message_data(data)
            try:
                await self._connection.send(data)
            except ConnectionError:
                __log__.info('Connection closed while sending data')
                self._start_reconnect()
                return

            for state in batch:
                if not isinstance(state, list):
                    if isinstance(state.request, TLRequest):
                        self._pending_state[state.msg_id] = state
                else:
                    for s in state:
                        if isinstance(s.request, TLRequest):
                            self._pending_state[s.msg_id] = s

            __log__.debug('Encrypted messages put in a queue to be sent')

    @_cancellable
    async def _recv_loop(self):
        """
        This loop is responsible for reading all incoming responses
        from the network, decrypting and handling or dispatching them.

        Besides `connect`, only this method ever receives data.
        """
        while self._user_connected and not self._reconnecting:
            __log__.debug('Receiving items from the network...')
            try:
                body = await self._connection.recv()
            except ConnectionError:
                __log__.info('Connection closed while receiving data')
                self._start_reconnect()
                return

            try:
                message = self._state.decrypt_message_data(body)
            except TypeNotFoundError as e:
                # Received object which we don't know how to deserialize
                __log__.info('Type %08x not found, remaining data %r',
                             e.invalid_constructor_id, e.remaining)
                continue
            except SecurityError as e:
                # A step while decoding had the incorrect data. This message
                # should not be considered safe and it should be ignored.
                __log__.warning('Security error while unpacking a '
                                'received message: %s', e)
                continue
            except BufferError as e:
                if isinstance(e, InvalidBufferError) and e.code == 404:
                    __log__.info('Broken authorization key; resetting')
                else:
                    __log__.warning('Invalid buffer %s', e)

                self.auth_key.key = None
                self._start_reconnect()
                return
            except Exception:
                __log__.exception('Unhandled error while receiving data')
                self._start_reconnect()
                return

            try:
                await self._process_message(message)
            except Exception:
                __log__.exception('Unhandled error while processing msgs')

    # Response Handlers

    async def _process_message(self, message):
        """
        Adds the given message to the list of messages that must be
        acknowledged and dispatches control to different ``_handle_*``
        method based on its type.
        """
        self._pending_ack.add(message.msg_id)
        handler = self._handlers.get(message.obj.CONSTRUCTOR_ID,
                                     self._handle_update)
        await handler(message)

    def _pop_states(self, msg_id):
        """
        Pops the states known to match the given ID from pending messages.

        This method should be used when the response isn't specific.
        """
        state = self._pending_state.pop(msg_id, None)
        if state:
            return [state]

        to_pop = []
        for state in self._pending_state.values():
            if state.container_id == msg_id:
                to_pop.append(state.msg_id)

        if to_pop:
            return [self._pending_state.pop(x) for x in to_pop]

        for ack in self._last_acks:
            if ack.msg_id == msg_id:
                return [ack]

        return []

    async def _handle_rpc_result(self, message):
        """
        Handles the result for Remote Procedure Calls:

            rpc_result#f35c6d01 req_msg_id:long result:bytes = RpcResult;

        This is where the future results for sent requests are set.
        """
        rpc_result = message.obj
        state = self._pending_state.pop(rpc_result.req_msg_id, None)
        __log__.debug('Handling RPC result for message %d',
                      rpc_result.req_msg_id)

        if not state:
            # TODO We should not get responses to things we never sent
            # However receiving a File() with empty bytes is "common".
            # See #658, #759 and #958. They seem to happen in a container
            # which contain the real response right after.
            try:
                with BinaryReader(rpc_result.body) as reader:
                    if not isinstance(reader.tgread_object(), upload.File):
                        raise ValueError('Not an upload.File')
            except (TypeNotFoundError, ValueError):
                __log__.info('Received response without parent request: {}'
                             .format(rpc_result.body))
            return

        if rpc_result.error:
            error = rpc_message_to_error(rpc_result.error, state.request)
            self._send_queue.append(
                RequestState(MsgsAck([state.msg_id]), loop=self._loop))

            if not state.future.cancelled():
                state.future.set_exception(error)
        else:
            with BinaryReader(rpc_result.body) as reader:
                result = state.request.read_result(reader)

            if not state.future.cancelled():
                state.future.set_result(result)

    async def _handle_container(self, message):
        """
        Processes the inner messages of a container with many of them:

            msg_container#73f1f8dc messages:vector<%Message> = MessageContainer;
        """
        __log__.debug('Handling container')
        for inner_message in message.obj.messages:
            await self._process_message(inner_message)

    async def _handle_gzip_packed(self, message):
        """
        Unpacks the data from a gzipped object and processes it:

            gzip_packed#3072cfa1 packed_data:bytes = Object;
        """
        __log__.debug('Handling gzipped data')
        with BinaryReader(message.obj.data) as reader:
            message.obj = reader.tgread_object()
            await self._process_message(message)

    async def _handle_update(self, message):
        __log__.debug('Handling update {}'
                      .format(message.obj.__class__.__name__))
        if self._update_callback:
            await self._update_callback(message.obj)

    async def _handle_pong(self, message):
        """
        Handles pong results, which don't come inside a ``rpc_result``
        but are still sent through a request:

            pong#347773c5 msg_id:long ping_id:long = Pong;
        """
        pong = message.obj
        __log__.debug('Handling pong for message %d', pong.msg_id)
        state = self._pending_state.pop(pong.msg_id, None)
        if state:
            state.future.set_result(pong)

    async def _handle_bad_server_salt(self, message):
        """
        Corrects the currently used server salt to use the right value
        before enqueuing the rejected message to be re-sent:

            bad_server_salt#edab447b bad_msg_id:long bad_msg_seqno:int
            error_code:int new_server_salt:long = BadMsgNotification;
        """
        bad_salt = message.obj
        __log__.debug('Handling bad salt for message %d', bad_salt.bad_msg_id)
        self._state.salt = bad_salt.new_server_salt
        states = self._pop_states(bad_salt.bad_msg_id)
        self._send_queue.extend(states)

        __log__.debug('%d message(s) will be resent', len(states))

    async def _handle_bad_notification(self, message):
        """
        Adjusts the current state to be correct based on the
        received bad message notification whenever possible:

            bad_msg_notification#a7eff811 bad_msg_id:long bad_msg_seqno:int
            error_code:int = BadMsgNotification;
        """
        bad_msg = message.obj
        states = self._pop_states(bad_msg.bad_msg_id)

        __log__.debug('Handling bad msg %s', bad_msg)
        if bad_msg.error_code in (16, 17):
            # Sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            to = self._state.update_time_offset(
                correct_msg_id=message.msg_id)
            __log__.info('System clock is wrong, set time offset to %ds', to)
        elif bad_msg.error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self._state._sequence += 64
        elif bad_msg.error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self._state._sequence -= 16
        else:
            for state in states:
                state.future.set_exception(
                    BadMessageError(state.request, bad_msg.error_code))
            return

        # Messages are to be re-sent once we've corrected the issue
        self._send_queue.extend(states)
        __log__.debug('%d messages will be resent due to bad msg', len(states))

    async def _handle_detailed_info(self, message):
        """
        Updates the current status with the received detailed information:

            msg_detailed_info#276d3ec6 msg_id:long answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/VvpCC6
        msg_id = message.obj.answer_msg_id
        __log__.debug('Handling detailed info for message %d', msg_id)
        self._pending_ack.add(msg_id)

    async def _handle_new_detailed_info(self, message):
        """
        Updates the current status with the received detailed information:

            msg_new_detailed_info#809db6df answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/G7DPsR
        msg_id = message.obj.answer_msg_id
        __log__.debug('Handling new detailed info for message %d', msg_id)
        self._pending_ack.add(msg_id)

    async def _handle_new_session_created(self, message):
        """
        Updates the current status with the received session information:

            new_session_created#9ec20908 first_msg_id:long unique_id:long
            server_salt:long = NewSession;
        """
        # TODO https://goo.gl/LMyN7A
        __log__.debug('Handling new session created')
        self._state.salt = message.obj.server_salt

    async def _handle_ack(self, message):
        """
        Handles a server acknowledge about our messages. Normally
        these can be ignored except in the case of ``auth.logOut``:

            auth.logOut#5717da40 = Bool;

        Telegram doesn't seem to send its result so we need to confirm
        it manually. No other request is known to have this behaviour.

        Since the ID of sent messages consisting of a container is
        never returned (unless on a bad notification), this method
        also removes containers messages when any of their inner
        messages are acknowledged.
        """
        ack = message.obj
        __log__.debug('Handling acknowledge for %s', str(ack.msg_ids))
        for msg_id in ack.msg_ids:
            state = self._pending_state.get(msg_id)
            if state and isinstance(state.request, LogOutRequest):
                del self._pending_state[msg_id]
                state.future.set_result(True)

    async def _handle_future_salts(self, message):
        """
        Handles future salt results, which don't come inside a
        ``rpc_result`` but are still sent through a request:

            future_salts#ae500895 req_msg_id:long now:int
            salts:vector<future_salt> = FutureSalts;
        """
        # TODO save these salts and automatically adjust to the
        # correct one whenever the salt in use expires.
        __log__.debug('Handling future salts for message %d', message.msg_id)
        state = self._pending_state.pop(message.msg_id, None)
        if state:
            state.future.set_result(message.obj)

    async def _handle_state_forgotten(self, message):
        """
        Handles both :tl:`MsgsStateReq` and :tl:`MsgResendReq` by
        enqueuing a :tl:`MsgsStateInfo` to be sent at a later point.
        """
        self._send_queue.append(RequestState(MsgsStateInfo(
            req_msg_id=message.msg_id, info=chr(1) * len(message.obj.msg_ids)),
            loop=self._loop))

    async def _handle_msg_all(self, message):
        """
        Handles :tl:`MsgsAllInfo` by doing nothing (yet).
        """
