import asyncio
import logging

from . import MTProtoPlainSender, authenticator
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
    MsgNewDetailedInfo, NewSessionCreated, MsgDetailedInfo, MsgsStateReq,
    MsgsStateInfo, MsgsAllInfo, MsgResendReq, upload
)

__log__ = logging.getLogger(__name__)


# Place this object in the send queue when a reconnection is needed
# so there is an item to read and we can early quit the loop, since
# without this it will block until there's something in the queue.
_reconnect_sentinel = object()


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
    def __init__(self, state, connection, loop, *,
                 retries=5, auto_reconnect=True, update_callback=None,
                 auth_key_callback=None, auto_reconnect_callback=None):
        self.state = state
        self._connection = connection
        self._loop = loop
        self._ip = None
        self._port = None
        self._retries = retries
        self._auto_reconnect = auto_reconnect
        self._update_callback = update_callback
        self._auth_key_callback = auth_key_callback
        self._auto_reconnect_callback = auto_reconnect_callback

        # Whether the user has explicitly connected or disconnected.
        #
        # If a disconnection happens for any other reason and it
        # was *not* user action then the pending messages won't
        # be cleared but on explicit user disconnection all the
        # pending futures should be cancelled.
        self._user_connected = False
        self._reconnecting = False
        self._disconnected = None

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

        # Similar to pending_messages but only for the last ack.
        # Ack can't be put in the messages because Telegram never
        # responds to acknowledges (they're just that, acknowledges),
        # so it would grow to infinite otherwise, but on bad salt it's
        # necessary to resend them just like everything else.
        self._last_ack = None

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

    def is_connected(self):
        return self._user_connected

    async def disconnect(self):
        """
        Cleanly disconnects the instance from the network, cancels
        all pending requests, and closes the send and receive loops.
        """
        if not self._user_connected:
            __log__.info('User is already disconnected!')
            return

        await self._disconnect()

    async def _disconnect(self, error=None):
        __log__.info('Disconnecting from {}...'.format(self._ip))
        self._user_connected = False
        try:
            __log__.debug('Closing current connection...')
            await self._connection.close()
        finally:
            __log__.debug('Cancelling {} pending message(s)...'
                          .format(len(self._pending_messages)))
            for message in self._pending_messages.values():
                if error and not message.future.done():
                    message.future.set_exception(error)
                else:
                    message.future.cancel()

            self._pending_messages.clear()
            self._pending_ack.clear()
            self._last_ack = None

            if self._send_loop_handle:
                __log__.debug('Cancelling the send loop...')
                self._send_loop_handle.cancel()

            if self._recv_loop_handle:
                __log__.debug('Cancelling the receive loop...')
                self._recv_loop_handle.cancel()

        __log__.info('Disconnection from {} complete!'.format(self._ip))
        if self._disconnected and not self._disconnected.done():
            if error:
                self._disconnected.set_exception(error)
            else:
                self._disconnected.set_result(None)

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
        if not self._user_connected:
            raise ConnectionError('Cannot send requests while disconnected')

        if utils.is_list_like(request):
            result = []
            after = None
            for r in request:
                message = self.state.create_message(
                    r, loop=self._loop, after=after)

                self._pending_messages[message.msg_id] = message
                self._send_queue.put_nowait(message)
                result.append(message.future)
                after = ordered and message
            return result
        else:
            message = self.state.create_message(request, loop=self._loop)
            self._pending_messages[message.msg_id] = message
            self._send_queue.put_nowait(message)
            return message.future

    @property
    def disconnected(self):
        """
        Future that resolves when the connection to Telegram
        ends, either by user action or in the background.
        """
        if self._disconnected is not None:
            return asyncio.shield(self._disconnected, loop=self._loop)
        else:
            raise ConnectionError('Sender was never connected')

    # Private methods

    async def _connect(self):
        """
        Performs the actual connection, retrying, generating the
        authorization key if necessary, and starting the send and
        receive loops.
        """
        __log__.info('Connecting to {}:{}...'.format(self._ip, self._port))
        for retry in range(1, self._retries + 1):
            try:
                __log__.debug('Connection attempt {}...'.format(retry))
                await self._connection.connect(self._ip, self._port)
            except (asyncio.TimeoutError, OSError) as e:
                __log__.warning('Attempt {} at connecting failed: {}: {}'
                                .format(retry, type(e).__name__, e))
            else:
                break
        else:
            raise ConnectionError('Connection to Telegram failed {} times'
                                  .format(self._retries))

        __log__.debug('Connection success!')
        if self.state.auth_key is None:
            plain = MTProtoPlainSender(self._connection)
            for retry in range(1, self._retries + 1):
                try:
                    __log__.debug('New auth_key attempt {}...'.format(retry))
                    self.state.auth_key, self.state.time_offset =\
                        await authenticator.do_authentication(plain)

                    if self._auth_key_callback:
                        self._auth_key_callback(self.state.auth_key)

                    break
                except (SecurityError, AssertionError) as e:
                    __log__.warning('Attempt {} at new auth_key failed: {}'
                                    .format(retry, e))
            else:
                e = ConnectionError('auth_key generation failed {} times'
                                    .format(self._retries))
                await self._disconnect(error=e)
                raise e

        __log__.debug('Starting send loop')
        self._send_loop_handle = self._loop.create_task(self._send_loop())

        __log__.debug('Starting receive loop')
        self._recv_loop_handle = self._loop.create_task(self._recv_loop())

        # First connection or manual reconnection after a failure
        if self._disconnected is None or self._disconnected.done():
            self._disconnected = self._loop.create_future()
        __log__.info('Connection to {} complete!'.format(self._ip))

    async def _reconnect(self):
        """
        Cleanly disconnects and then reconnects.
        """
        self._reconnecting = True
        self._send_queue.put_nowait(_reconnect_sentinel)

        __log__.debug('Awaiting for the send loop before reconnecting...')
        await self._send_loop_handle

        __log__.debug('Awaiting for the receive loop before reconnecting...')
        await self._recv_loop_handle

        __log__.debug('Closing current connection...')
        await self._connection.close()

        self._reconnecting = False

        retries = self._retries if self._auto_reconnect else 0
        for retry in range(1, retries + 1):
            try:
                await self._connect()
                for m in self._pending_messages.values():
                    self._send_queue.put_nowait(m)

                if self._auto_reconnect_callback:
                    self._loop.create_task(self._auto_reconnect_callback())

                break
            except ConnectionError:
                __log__.info('Failed reconnection retry %d/%d', retry, retries)
        else:
            __log__.error('Failed to reconnect automatically.')
            await self._disconnect(error=ConnectionError())

    def _start_reconnect(self):
        """Starts a reconnection in the background."""
        if self._user_connected:
            self._loop.create_task(self._reconnect())

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
                self._last_ack = self.state.create_message(
                    MsgsAck(list(self._pending_ack)), loop=self._loop
                )
                self._send_queue.put_nowait(self._last_ack)
                self._pending_ack.clear()

            messages = await self._send_queue.get()
            if messages == _reconnect_sentinel:
                if self._reconnecting:
                    break
                else:
                    continue

            if isinstance(messages, list):
                message = self.state.create_message(
                    MessageContainer(messages), loop=self._loop)

                self._pending_messages[message.msg_id] = message
                self._pending_containers.append(message)
            else:
                message = messages
                messages = [message]

            __log__.debug(
                'Packing %d outgoing message(s) %s...', len(messages),
                ', '.join(x.obj.__class__.__name__ for x in messages)
            )
            body = self.state.pack_message(message)

            while not any(m.future.cancelled() for m in messages):
                try:
                    __log__.debug('Sending {} bytes...'.format(len(body)))
                    await self._connection.send(body)
                    break
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    if isinstance(e, ConnectionError):
                        __log__.info('Connection reset while sending %s', e)
                    elif isinstance(e, OSError):
                        __log__.warning('OSError while sending %s', e)
                    else:
                        __log__.exception('Unhandled exception while receiving')
                        await asyncio.sleep(1, loop=self._loop)

                    self._start_reconnect()
                    break
            else:
                # Remove the cancelled messages from pending
                __log__.info('Some futures were cancelled, aborted send')
                self._clean_containers([m.msg_id for m in messages])
                for m in messages:
                    if m.future.cancelled():
                        self._pending_messages.pop(m.msg_id, None)
                    else:
                        self._send_queue.put_nowait(m)

            __log__.debug('Outgoing messages {} sent!'
                          .format(', '.join(str(m.msg_id) for m in messages)))

    async def _recv_loop(self):
        """
        This loop is responsible for reading all incoming responses
        from the network, decrypting and handling or dispatching them.

        Besides `connect`, only this method ever receives data.
        """
        while self._user_connected and not self._reconnecting:
            try:
                __log__.debug('Receiving items from the network...')
                body = await self._connection.recv()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                if isinstance(e, ConnectionError):
                    __log__.info('Connection reset while receiving %s', e)
                elif isinstance(e, OSError):
                    __log__.warning('OSError while receiving %s', e)
                else:
                    __log__.exception('Unhandled exception while receiving')
                    await asyncio.sleep(1, loop=self._loop)

                self._start_reconnect()
                break

            # TODO Check salt, session_id and sequence_number
            __log__.debug('Decoding packet of %d bytes...', len(body))
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
                self._start_reconnect()
                break
            except SecurityError as e:
                # A step while decoding had the incorrect data. This message
                # should not be considered safe and it should be ignored.
                __log__.warning('Security error while unpacking a '
                                'received message: {}'.format(e))
                continue
            except TypeNotFoundError as e:
                # The payload inside the message was not a known TLObject.
                __log__.info('Server replied with an unknown type {:08x}: {!r}'
                             .format(e.invalid_constructor_id, e.remaining))
                continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                __log__.exception('Unhandled exception while unpacking %s',e)
                await asyncio.sleep(1, loop=self._loop)
            else:
                try:
                    await self._process_message(message)
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    __log__.exception('Unhandled exception while '
                                      'processing %s', message)
                    await asyncio.sleep(1, loop=self._loop)

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
        __log__.debug('Handling RPC result for message %d',
                      rpc_result.req_msg_id)

        if not message:
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
            error = rpc_message_to_error(rpc_result.error)
            self._send_queue.put_nowait(self.state.create_message(
                MsgsAck([message.msg_id]), loop=self._loop
            ))

            if not message.future.cancelled():
                message.future.set_exception(error)
        else:
            # TODO Would be nice to avoid accessing a per-obj read_result
            # Instead have a variable that indicated how the result should
            # be read (an enum) and dispatch to read the result, mostly
            # always it's just a normal TLObject.
            with BinaryReader(rpc_result.body) as reader:
                result = message.obj.read_result(reader)

            if not message.future.cancelled():
                message.future.set_result(result)

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
            self._update_callback(message.obj)

    async def _handle_pong(self, message):
        """
        Handles pong results, which don't come inside a ``rpc_result``
        but are still sent through a request:

            pong#347773c5 msg_id:long ping_id:long = Pong;
        """
        pong = message.obj
        __log__.debug('Handling pong for message %d', pong.msg_id)
        message = self._pending_messages.pop(pong.msg_id, None)
        if message:
            message.future.set_result(pong)

    async def _handle_bad_server_salt(self, message):
        """
        Corrects the currently used server salt to use the right value
        before enqueuing the rejected message to be re-sent:

            bad_server_salt#edab447b bad_msg_id:long bad_msg_seqno:int
            error_code:int new_server_salt:long = BadMsgNotification;
        """
        bad_salt = message.obj
        __log__.debug('Handling bad salt for message %d', bad_salt.bad_msg_id)
        self.state.salt = bad_salt.new_server_salt
        if self._last_ack and bad_salt.bad_msg_id == self._last_ack.msg_id:
            self._send_queue.put_nowait(self._last_ack)
            return

        try:
            self._send_queue.put_nowait(
                self._pending_messages[bad_salt.bad_msg_id])
        except KeyError:
            # May be MsgsAck, those are not saved in pending messages
            __log__.info('Message %d not resent due to bad salt',
                         bad_salt.bad_msg_id)

    async def _handle_bad_notification(self, message):
        """
        Adjusts the current state to be correct based on the
        received bad message notification whenever possible:

            bad_msg_notification#a7eff811 bad_msg_id:long bad_msg_seqno:int
            error_code:int = BadMsgNotification;
        """
        bad_msg = message.obj
        msg = self._pending_messages.get(bad_msg.bad_msg_id)

        __log__.debug('Handling bad msg %s', bad_msg)
        if bad_msg.error_code in (16, 17):
            # Sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            to = self.state.update_time_offset(correct_msg_id=message.msg_id)
            __log__.info('System clock is wrong, set time offset to %ds', to)

            # Correct the msg_id *of the message to resend*, not all.
            #
            # If we correct them all, new "bad message" would not find
            # the old invalid IDs, causing all awaits to never finish.
            if msg:
                del self._pending_messages[msg.msg_id]
                self.state.update_message_id(msg)
                self._pending_messages[msg.msg_id] = msg

        elif bad_msg.error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self.state._sequence += 64
        elif bad_msg.error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self.state._sequence -= 16
        else:
            if msg:
                del self._pending_messages[msg.msg_id]
                msg.future.set_exception(BadMessageError(bad_msg.error_code))
            return

        # Messages are to be re-sent once we've corrected the issue
        if msg:
            self._send_queue.put_nowait(msg)
        else:
            # May be MsgsAck, those are not saved in pending messages
            __log__.info('Message %d not resent due to bad msg',
                         bad_msg.bad_msg_id)

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
        ack = message.obj
        __log__.debug('Handling acknowledge for %s', str(ack.msg_ids))
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
        __log__.debug('Handling future salts for message %d', message.msg_id)
        msg = self._pending_messages.pop(message.msg_id, None)
        if msg:
            msg.future.set_result(message.obj)

    async def _handle_state_forgotten(self, message):
        """
        Handles both :tl:`MsgsStateReq` and :tl:`MsgResendReq` by
        enqueuing a :tl:`MsgsStateInfo` to be sent at a later point.
        """
        self.send(MsgsStateInfo(req_msg_id=message.msg_id,
                                info=chr(1) * len(message.obj.msg_ids)))

    async def _handle_msg_all(self, message):
        """
        Handles :tl:`MsgsAllInfo` by doing nothing (yet).
        """


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
        if self.empty() or result == _reconnect_sentinel or\
                isinstance(result.obj, MessageContainer):
            return result

        size = result.size()
        result = [result]
        while not self.empty():
            item = self.get_nowait()
            if (item == _reconnect_sentinel or
                isinstance(item.obj, MessageContainer)
                    or size + item.size() > MessageContainer.MAXIMUM_SIZE):
                self.put_nowait(item)
                break
            else:
                size += item.size()
                result.append(item)

        return result
