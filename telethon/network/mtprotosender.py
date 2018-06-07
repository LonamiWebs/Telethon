import asyncio
import logging

from .connection import ConnectionTcpFull
from .. import helpers, utils
from ..errors import BadMessageError, TypeNotFoundError, rpc_message_to_error
from ..extensions import BinaryReader
from ..tl import TLMessage, MessageContainer, GzipPacked
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
    def __init__(self, session):
        self.session = session
        self._connection = ConnectionTcpFull()

        # Whether the user has explicitly connected or disconnected.
        #
        # If a disconnection happens for any other reason and it
        # was *not* user action then the pending messages won't
        # be cleared but on explicit user disconnection all the
        # pending futures should be cancelled.
        self._user_connected = False

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
        # its inner requests are acknowledged. For this purpose we save
        # {msg_id: container}.
        self._pending_containers = []

        # We need to acknowledge every response from Telegram
        self._pending_ack = set()

        # Jump table from response ID to method that handles it
        self._handlers = {
            0xf35c6d01: self._handle_rpc_result,
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
            return

        # TODO Generate auth_key if needed
        async with self._send_lock:
            await self._connection.connect(ip, port)
        self._user_connected = True
        self._send_loop_handle = asyncio.ensure_future(self._send_loop())
        self._recv_loop_handle = asyncio.ensure_future(self._recv_loop())

    async def disconnect(self):
        """
        Cleanly disconnects the instance from the network, cancels
        all pending requests, and closes the send and receive loops.
        """
        if not self._user_connected:
            return

        self._user_connected = False
        try:
            async with self._send_lock:
                await self._connection.close()
        except:
            __log__.exception('Ignoring exception upon disconnection')
        finally:
            for message in self._pending_messages.values():
                message.future.cancel()

            self._pending_messages.clear()
            self._pending_ack.clear()
            self._send_loop_handle.cancel()
            self._recv_loop_handle.cancel()

    async def send(self, request, ordered=False):
        """
        This method enqueues the given request to be sent.

        The request will be wrapped inside a `TLMessage` until its
        response arrives, and the `Future` response of the `TLMessage`
        is immediately returned so that one can further ``await`` it:

        .. code-block:: python

            async def method():
                # Sending (enqueued for the send loop)
                future = await sender.send(request)
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
        # TODO Perhaps this method should be synchronous and just return
        # a `Future` that you need to further ``await`` instead of the
        # currently double ``await (await send())``?
        if utils.is_list_like(request):
            if not ordered:
                # False-y values must be None to do after_id = ordered and ...
                ordered = None

            result = []
            after_id = None
            for r in request:
                message = TLMessage(self.session, r, after_id=after_id)
                self._pending_messages[message.msg_id] = message
                after_id = ordered and message.msg_id
                await self._send_queue.put(message)
                result.append(message.future)
            return result
        else:
            message = TLMessage(self.session, request)
            self._pending_messages[message.msg_id] = message
            await self._send_queue.put(message)
            return message.future

    # Loops

    async def _send_loop(self):
        """
        This loop is responsible for popping items off the send
        queue, encrypting them, and sending them over the network.

        Besides `connect`, only this method ever sends data.
        """
        while self._user_connected:
            if self._pending_ack:
                await self._send_queue.put(TLMessage(
                    self.session, MsgsAck(list(self._pending_ack))))
                self._pending_ack.clear()

            message = await self._send_queue.get()
            if isinstance(message, list):
                message = TLMessage(self.session, MessageContainer(message))
                self._pending_messages[message.msg_id] = message
                self._pending_containers.append(message)

            body = helpers.pack_message(self.session, message)

            # TODO Handle exceptions
            async with self._send_lock:
                await self._connection.send(body)

    async def _recv_loop(self):
        """
        This loop is responsible for reading all incoming responses
        from the network, decrypting and handling or dispatching them.

        Besides `connect`, only this method ever receives data.
        """
        while self._user_connected:
            # TODO Handle exceptions
            async with self._recv_lock:
                body = await self._connection.recv()

            # TODO Check salt, session_id and sequence_number
            message, remote_msg_id, remote_seq = helpers.unpack_message(
                self.session, body)

            with BinaryReader(message) as reader:
                await self._process_message(remote_msg_id, remote_seq, reader)

    # Response Handlers

    async def _process_message(self, msg_id, seq, reader):
        """
        Adds the given message to the list of messages that must be
        acknowledged and dispatches control to different ``_handle_*``
        method based on its type.
        """
        self._pending_ack.add(msg_id)
        code = reader.read_int(signed=False)
        reader.seek(-4)
        handler = self._handlers.get(code, self._handle_update)
        await handler(msg_id, seq, reader)

    async def _handle_rpc_result(self, msg_id, seq, reader):
        """
        Handles the result for Remote Procedure Calls:

            rpc_result#f35c6d01 req_msg_id:long result:bytes = RpcResult;

        This is where the future results for sent requests are set.
        """
        # TODO Don't make this a special cased object
        reader.read_int(signed=False)  # code
        message_id = reader.read_long()
        inner_code = reader.read_int(signed=False)
        reader.seek(-4)

        message = self._pending_messages.pop(message_id, None)
        if inner_code == 0x2144ca19:  # RPC Error
            reader.seek(4)
            if self.session.report_errors and message:
                error = rpc_message_to_error(
                    reader.read_int(), reader.tgread_string(),
                    report_method=type(message.request).CONSTRUCTOR_ID
                )
            else:
                error = rpc_message_to_error(
                    reader.read_int(), reader.tgread_string()
                )

            await self._send_queue.put(
                TLMessage(self.session, MsgsAck([msg_id])))

            if not message.future.cancelled():
                message.future.set_exception(error)
            return
        elif message:
            if inner_code == GzipPacked.CONSTRUCTOR_ID:
                with BinaryReader(GzipPacked.read(reader)) as compressed_reader:
                    result = message.request.read_result(compressed_reader)
            else:
                result = message.request.read_result(reader)

            self.session.process_entities(result)
            if not message.future.cancelled():
                message.future.set_result(result)
            return
        else:
            # TODO We should not get responses to things we never sent
            try:
                if inner_code == GzipPacked.CONSTRUCTOR_ID:
                    with BinaryReader(GzipPacked.read(reader)) as creader:
                        obj = creader.tgread_object()
                else:
                    obj = reader.tgread_object()
            except TypeNotFoundError:
                pass

    async def _handle_container(self, msg_id, seq, reader):
        """
        Processes the inner messages of a container with many of them:

            msg_container#73f1f8dc messages:vector<%Message> = MessageContainer;
        """
        for inner_msg_id, _, inner_len in MessageContainer.iter_read(reader):
            next_position = reader.tell_position() + inner_len
            await self._process_message(inner_msg_id, seq, reader)
            reader.set_position(next_position)  # Ensure reading correctly

    async def _handle_gzip_packed(self, msg_id, seq, reader):
        """
        Unpacks the data from a gzipped object and processes it:

            gzip_packed#3072cfa1 packed_data:bytes = Object;
        """
        with BinaryReader(GzipPacked.read(reader)) as compressed_reader:
            await self._process_message(msg_id, seq, compressed_reader)

    async def _handle_update(self, msg_id, seq, reader):
        try:
            obj = reader.tgread_object()
        except TypeNotFoundError:
            return

        # TODO Further handling of the update
        self.session.process_entities(obj)

    async def _handle_pong(self, msg_id, seq, reader):
        """
        Handles pong results, which don't come inside a ``rpc_result``
        but are still sent through a request:

            pong#347773c5 msg_id:long ping_id:long = Pong;
        """
        pong = reader.tgread_object()
        message = self._pending_messages.pop(pong.msg_id, None)
        if message:
            message.future.set_result(pong)

    async def _handle_bad_server_salt(self, msg_id, seq, reader):
        """
        Corrects the currently used server salt to use the right value
        before enqueuing the rejected message to be re-sent:

            bad_server_salt#edab447b bad_msg_id:long bad_msg_seqno:int
            error_code:int new_server_salt:long = BadMsgNotification;
        """
        bad_salt = reader.tgread_object()
        self.session.salt = bad_salt.new_server_salt
        self.session.save()
        await self._send_queue.put(self._pending_messages[bad_salt.bad_msg_id])

    async def _handle_bad_notification(self, msg_id, seq, reader):
        """
        Adjusts the current state to be correct based on the
        received bad message notification whenever possible:

            bad_msg_notification#a7eff811 bad_msg_id:long bad_msg_seqno:int
            error_code:int = BadMsgNotification;
        """
        bad_msg = reader.tgread_object()
        if bad_msg.error_code in (16, 17):
            # Sent msg_id too low or too high (respectively).
            # Use the current msg_id to determine the right time offset.
            self.session.update_time_offset(correct_msg_id=msg_id)
        elif bad_msg.error_code == 32:
            # msg_seqno too low, so just pump it up by some "large" amount
            # TODO A better fix would be to start with a new fresh session ID
            self.session.sequence += 64
        elif bad_msg.error_code == 33:
            # msg_seqno too high never seems to happen but just in case
            self.session.sequence -= 16
        else:
            msg = self._pending_messages.pop(bad_msg.bad_msg_id, None)
            if msg:
                msg.future.set_exception(BadMessageError(bad_msg.error_code))
            return

        # Messages are to be re-sent once we've corrected the issue
        await self._send_queue.put(self._pending_messages[bad_msg.bad_msg_id])

    async def _handle_detailed_info(self, msg_id, seq, reader):
        """
        Updates the current status with the received detailed information:

            msg_detailed_info#276d3ec6 msg_id:long answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/VvpCC6
        self._pending_ack.add(reader.tgread_object().answer_msg_id)

    async def _handle_new_detailed_info(self, msg_id, seq, reader):
        """
        Updates the current status with the received detailed information:

            msg_new_detailed_info#809db6df answer_msg_id:long
            bytes:int status:int = MsgDetailedInfo;
        """
        # TODO https://goo.gl/G7DPsR
        self._pending_ack.add(reader.tgread_object().answer_msg_id)

    async def _handle_new_session_created(self, msg_id, seq, reader):
        """
        Updates the current status with the received session information:

            new_session_created#9ec20908 first_msg_id:long unique_id:long
            server_salt:long = NewSession;
        """
        # TODO https://goo.gl/LMyN7A
        self.session.salt = reader.tgread_object().server_salt

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
            for msg in message.request.messages:
                if msg.msg_id in msg_ids:
                    del self._pending_containers[i]
                    del self._pending_messages[message.msg_id]
                    break

    async def _handle_ack(self, msg_id, seq, reader):
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
        ack = reader.tgread_object()
        if self._pending_containers:
            self._clean_containers(ack.msg_ids)

        for msg_id in ack.msg_ids:
            msg = self._pending_messages.get(msg_id, None)
            if msg and isinstance(msg.request, LogOutRequest):
                del self._pending_messages[msg_id]
                msg.future.set_result(True)

    async def _handle_future_salts(self, msg_id, seq, reader):
        """
        Handles future salt results, which don't come inside a
        ``rpc_result`` but are still sent through a request:

            future_salts#ae500895 req_msg_id:long now:int
            salts:vector<future_salt> = FutureSalts;
        """
        # TODO save these salts and automatically adjust to the
        # correct one whenever the salt in use expires.
        salts = reader.tgread_object()
        msg = self._pending_messages.pop(msg_id, None)
        if msg:
            msg.future.set_result(salts)


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
        if self.empty() or isinstance(result.request, MessageContainer):
            return result

        result = [result]
        while not self.empty():
            item = self.get_nowait()
            if isinstance(item.request, MessageContainer):
                await self.put(item)
                break
            else:
                result.append(item)

        return result
