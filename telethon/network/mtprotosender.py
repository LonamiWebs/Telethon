import asyncio
import logging

from . import MTProtoPlainSender, authenticator
from .connection import ConnectionTcpFull
from .. import utils
from ..errors import (
    BadMessageError, TypeNotFoundError, BrokenAuthKeyError, SecurityError,
    rpc_message_to_error
)
from ..extensions import BinaryReader
from ..tl.core import RpcResult, MessageContainer, GzipPacked
from ..tl.functions.auth import LogOutRequest
from ..tl.types import (
    MsgsAck, Pong, BadServerSalt, BadMsgNotification, FutureSalts,
    MsgNewDetailedInfo, NewSessionCreated, MsgDetailedInfo
)

__log__ = logging.getLogger(__name__)


# TODO Create some kind of "ReconnectionPolicy" that allows specifying
# what should be done in case of some errors, with some sane defaults.
# For instance, should all messages be set with an error upon network
# loss? Should we try reconnecting forever? A certain amount of times?
# A timeout? What about recoverable errors, like connection reset?
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
    def __init__(self, state, retries=5):
        self.state = state
        self._connection = ConnectionTcpFull()
        self._ip = None
        self._port = None
        self._retries = retries

        # Whether the user has explicitly connected or disconnected.
        #
        # If a disconnection happens for any other reason and it
        # was *not* user action then the pending messages won't
        # be cleared but on explicit user disconnection all the
        # pending futures should be cancelled.
        self._user_connected = False
        self._reconnecting = False

        # Send and receive calls must be atomic
        self._send_lock = asyncio.Lock()
        self._recv_lock = asyncio.Lock()

        # We need to join the loops upon disconnection
        self._send_loop_handle = None
        self._recv_loop_handle = None

        # Sending something shouldn't block
        self._send_queue = _ContainerQueue()

        # Telegram responds to messages out of order. Keep
        # {id: Message} to set their Future result upon arrival.
        self._pending_messages = {}

        # Containers are accepted or rejected as a whole when any of
        # its inner requests are acknowledged. For this purpose we
        # all the sent containers here.
        self._pending_containers = []

        # We need to acknowledge every response from Telegram
        self._pending_ack = set()

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
            FutureSalts.CONSTRUCTOR_ID: self._handle_future_salts
        }

    # Public API

    async def connect(self, ip, port):
        """
        Connects to the specified ``ip:port``, and generates a new
        authorization key for the `MTProtoSender.session` if it does
        not exist yet.
        """
        if self._user_connected:
            __log__.info('User is already connected!')
            return

        self._ip = ip
        self._port = port
        self._user_connected = True
        await self._connect()

    async def disconnect(self):
        """
        Cleanly disconnects the instance from the network, cancels
        all pending requests, and closes the send and receive loops.
        """
        if not self._user_connected:
            __log__.info('User is already disconnected!')
            return

        __log__.info('Disconnecting from {}...'.format(self._ip))
        self._user_connected = False
        try:
            __log__.debug('Closing current connection...')
            async with self._send_lock:
                await self._connection.close()
        finally:
            __log__.debug('Cancelling {} pending message(s)...'
                          .format(len(self._pending_messages)))
            for message in self._pending_messages.values():
                message.future.cancel()

            self._pending_messages.clear()
            self._pending_ack.clear()

            __log__.debug('Cancelling the send loop...')
            self._send_loop_handle.cancel()

            __log__.debug('Cancelling the receive loop...')
            self._recv_loop_handle.cancel()

        __log__.info('Disconnection from {} complete!'.format(self._ip))

    def send(self, request, ordered=False):
        """
        This method enqueues the given request to be sent.

        The request will be wrapped inside a `TLMessage` until its
        response arrives, and the `Future` response of the `TLMessage`
        is immediately returned so that one can further ``await`` it:

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
        if utils.is_list_like(request):
            result = []
            after = None
            for r in request:
                message = self.state.create_message(r, after=after)
                self._pending_messages[message.msg_id] = message
                self._send_queue.put_nowait(message)
                result.append(message.future)
                after = ordered and message
            return result
        else:
            message = self.state.create_message(request)
            self._pending_messages[message.msg_id] = message
            self._send_queue.put_nowait(message)
            return message.future

    # Private methods

    async def _connect(self):
        """
        Performs the actual connection, retrying, generating the
        authorization key if necessary, and starting the send and
        receive loops.
        """
        __log__.info('Connecting to {}:{}...'.format(self._ip, self._port))
        _last_error = ConnectionError()
        for retry in range(1, self._retries + 1):
            try:
                __log__.debug('Connection attempt {}...'.format(retry))
                async with self._send_lock:
                    await self._connection.connect(self._ip, self._port)
            except OSError as e:
                _last_error = e
                __log__.warning('Attempt {} at connecting failed: {}'
                                .format(retry, e))
            else:
                break
        else:
            raise _last_error

        __log__.debug('Connection success!')
        if self.state.auth_key is None:
            _last_error = SecurityError()
            plain = MTProtoPlainSender(self._connection)
            for retry in range(1, self._retries + 1):
                try:
                    __log__.debug('New auth_key attempt {}...'.format(retry))
                    self.state.auth_key, self.state.time_offset =\
                        await authenticator.do_authentication(plain)
                except (SecurityError, AssertionError) as e:
                    _last_error = e
                    __log__.warning('Attempt {} at new auth_key failed: {}'
                                    .format(retry, e))
                else:
                    break
            else:
                raise _last_error

        __log__.debug('Starting send loop')
        self._send_loop_handle = asyncio.ensure_future(self._send_loop())
        __log__.debug('Starting receive loop')
        self._recv_loop_handle = asyncio.ensure_future(self._recv_loop())
        __log__.info('Connection to {} complete!'.format(self._ip))

    async def _reconnect(self):
        """
        Cleanly disconnects and then reconnects.
        """
        self._reconnecting = True

        __log__.debug('Awaiting for the send loop before reconnecting...')
        await self._send_loop_handle

        __log__.debug('Awaiting for the receive loop before reconnecting...')
        await self._recv_loop_handle

        __log__.debug('Closing current connection...')
        async with self._send_lock:
            await self._connection.close()

        self._reconnecting = False
        await self._connect()

    def _clean_containers(self, msg_ids):
        """
        Helper method to clean containers from the pending messages
        once a wrapped msg_id of them has been acknowledged.

        This is the only way we can resend TLMessage(MessageContainer)
        on bad notifications and also mark them as received once any
        of their inner TLMessage is acknowledged.
        """
        for i in reversed(range(len(self._pending_containers))):
            message = self._pending_containers[i]
            for msg in message.obj.messages:
                if msg.msg_id in msg_ids:
                    del self._pending_containers[i]
                    del self._pending_messages[message.msg_id]
                    break

    # Loops

    async def _send_loop(self):
        """
        This loop is responsible for popping items off the send
        queue, encrypting them, and sending them over the network.

        Besides `connect`, only this method ever sends data.
        """
        while self._user_connected and not self._reconnecting:
            if self._pending_ack:
                self._send_queue.put_nowait(self.state.create_message(
                    MsgsAck(list(self._pending_ack))
                ))
                self._pending_ack.clear()

            messages = await self._send_queue.get()
            if isinstance(messages, list):
                message = self.state.create_message(MessageContainer(messages))
                self._pending_messages[message.msg_id] = message
                self._pending_containers.append(message)
            else:
                message = messages
                messages = [message]

            __log__.debug('Packing {} outgoing message(s)...'
                          .format(len(messages)))
            body = self.state.pack_message(message)

            while not any(m.future.cancelled() for m in messages):
                try:
                    async with self._send_lock:
                        __log__.debug('Sending {} bytes...', len(body))
                        await self._connection.send(body)
                    break
                # TODO Are there more exceptions besides timeout?
                except asyncio.TimeoutError:
                    continue
            else:
                # Remove the cancelled messages from pending
                __log__.info('Some futures were cancelled, aborted send')
                self._clean_containers([m.msg_id for m in messages])
                for m in messages:
                    if m.future.cancelled():
                        self._pending_messages.pop(m.msg_id, None)
                    else:
                        self._send_queue.put_nowait(m)

            __log__.debug('Outgoing messages sent!')

    async def _recv_loop(self):
        """
        This loop is responsible for reading all incoming responses
        from the network, decrypting and handling or dispatching them.

        Besides `connect`, only this method ever receives data.
        """
        while self._user_connected and not self._reconnecting:
            # TODO Are there more exceptions besides timeout?
            # Disconnecting or switching off WiFi only resulted in
            # timeouts, and once the network was back it continued
            # on its own after a short delay.
            try:
                __log__.debug('Receiving items from the network...')
                async with self._recv_lock:
                    body = await self._connection.recv()
            except asyncio.TimeoutError:
                # TODO If nothing is received for a minute, send a request
                continue
            except ConnectionError as e:
                __log__.info('Connection reset while receiving: {}'.format(e))
                asyncio.ensure_future(self._reconnect())
                break

            # TODO Check salt, session_id and sequence_number
            __log__.debug('Decoding packet of {} bytes...'.format(len(body)))
            try:
                message = self.state.unpack_message(body)
            except (BrokenAuthKeyError, BufferError) as e:
                # The authorization key may be broken if a message was
                # sent malformed, or if the authkey truly is corrupted.
                #
                # There may be a buffer error if Telegram's response was too
                # short and hence not understood. Reset the authorization key
                # and try again in either case.
                #
                # TODO Is it possible to detect malformed messages vs
                # an actually broken authkey?
                __log__.warning('Broken authorization key?: {}'.format(e))
                self.state.auth_key = None
                asyncio.ensure_future(self._reconnect())
                break
            except SecurityError as e:
                # A step while decoding had the incorrect data. This message
                # should not be considered safe and it should be ignored.
                __log__.warning('Security error while unpacking a '
                                'received message:'.format(e))
                continue
            except TypeNotFoundError as e:
                # The payload inside the message was not a known TLObject.
                __log__.info('Server replied with an unknown type {:08x}: {!r}'
                             .format(e.invalid_constructor_id, e.remaining))
            else:
                await self._process_message(message)

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

    async def _handle_rpc_result(self, message):
        """
        Handles the result for Remote Procedure Calls:

            rpc_result#f35c6d01 req_msg_id:long result:bytes = RpcResult;

        This is where the future results for sent requests are set.
        """
        rpc_result = message.obj
        message = self._pending_messages.pop(rpc_result.req_msg_id, None)
        __log__.debug('Handling RPC result for message {}'
                      .format(rpc_result.req_msg_id))

        if rpc_result.error:
            # TODO Report errors if possible/enabled
            error = rpc_message_to_error(rpc_result.error)
            self._send_queue.put_nowait(self.state.create_message(
                MsgsAck([message.msg_id])
            ))

            if not message.future.cancelled():
                message.future.set_exception(error)
            return
        elif message:
            with BinaryReader(rpc_result.body) as reader:
                result = message.obj.read_result(reader)

            # TODO Process entities
            if not message.future.cancelled():
                message.future.set_result(result)
            return
        else:
            # TODO We should not get responses to things we never sent
            __log__.info('Received response without parent request: {}'
                         .format(rpc_result.body))

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

        # TODO Further handling of the update
        # TODO Process entities

    async def _handle_pong(self, message):
        """
        Handles pong results, which don't come inside a ``rpc_result``
        but are still sent through a request:

            pong#347773c5 msg_id:long ping_id:long = Pong;
        """
        __log__.debug('Handling pong')
        pong = message.obj
        message = self._pending_messages.pop(pong.msg_id, None)
        if message:
            message.future.set_result(pong.obj)

    async def _handle_bad_server_salt(self, message):
        """
        Corrects the currently used server salt to use the right value
        before enqueuing the rejected message to be re-sent:

            bad_server_salt#edab447b bad_msg_id:long bad_msg_seqno:int
            error_code:int new_server_salt:long = BadMsgNotification;
        """
        __log__.debug('Handling bad salt')
        bad_salt = message.obj
        self.state.salt = bad_salt.new_server_salt
        self._send_queue.put_nowait(self._pending_messages[bad_salt.bad_msg_id])

    async def _handle_bad_notification(self, message):
        """
        Adjusts the current state to be correct based on the
        received bad message notification whenever possible:

            bad_msg_notification#a7eff811 bad_msg_id:long bad_msg_seqno:int
            error_code:int = BadMsgNotification;
        """
        __log__.debug('Handling bad message')
        bad_msg = message.obj
        if bad_msg.error_code in (16, 17):
            # Sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            self.state.update_time_offset(correct_msg_id=message.msg_id)
        elif bad_msg.error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self.state._sequence += 64
        elif bad_msg.error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self.state._sequence -= 16
        else:
            msg = self._pending_messages.pop(bad_msg.bad_msg_id, None)
            if msg:
                msg.future.set_exception(BadMessageError(bad_msg.error_code))
            return

        # Messages are to be re-sent once we've corrected the issue
        self._send_queue.put_nowait(self._pending_messages[bad_msg.bad_msg_id])

    async def _handle_detailed_info(self, message):
        """
        Updates the current status with the received detailed information:

            msg_detailed_info#276d3ec6 msg_id:long answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/VvpCC6
        __log__.debug('Handling detailed info')
        self._pending_ack.add(message.obj.answer_msg_id)

    async def _handle_new_detailed_info(self, message):
        """
        Updates the current status with the received detailed information:

            msg_new_detailed_info#809db6df answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/G7DPsR
        __log__.debug('Handling new detailed info')
        self._pending_ack.add(message.obj.answer_msg_id)

    async def _handle_new_session_created(self, message):
        """
        Updates the current status with the received session information:

            new_session_created#9ec20908 first_msg_id:long unique_id:long
            server_salt:long = NewSession;
        """
        # TODO https://goo.gl/LMyN7A
        __log__.debug('Handling new session created')
        self.state.salt = message.obj.server_salt

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
        __log__.debug('Handling acknowledge')
        ack = message.obj
        if self._pending_containers:
            self._clean_containers(ack.msg_ids)

        for msg_id in ack.msg_ids:
            msg = self._pending_messages.get(msg_id, None)
            if msg and isinstance(msg.obj, LogOutRequest):
                del self._pending_messages[msg_id]
                msg.future.set_result(True)

    async def _handle_future_salts(self, message):
        """
        Handles future salt results, which don't come inside a
        ``rpc_result`` but are still sent through a request:

            future_salts#ae500895 req_msg_id:long now:int
            salts:vector<future_salt> = FutureSalts;
        """
        # TODO save these salts and automatically adjust to the
        # correct one whenever the salt in use expires.
        __log__.debug('Handling future salts')
        msg = self._pending_messages.pop(message.msg_id, None)
        if msg:
            msg.future.set_result(message.obj)


class _ContainerQueue(asyncio.Queue):
    """
    An asyncio queue that's aware of `MessageContainer` instances.

    The `get` method returns either a single `TLMessage` or a list
    of them that should be turned into a new `MessageContainer`.

    Instances of this class can be replaced with the simpler
    ``asyncio.Queue`` when needed for testing purposes, and
    a list won't be returned in said case.
    """
    async def get(self):
        result = await super().get()
        if self.empty() or isinstance(result.obj, MessageContainer):
            return result

        result = [result]
        while not self.empty():
            item = self.get_nowait()
            if isinstance(item.obj, MessageContainer):
                self.put_nowait(item)
                break
            else:
                result.append(item)

        return result
