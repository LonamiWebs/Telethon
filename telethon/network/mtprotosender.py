import asyncio
import logging

from .connection import ConnectionTcpFull
from .. import helpers
from ..errors import rpc_message_to_error
from ..extensions import BinaryReader
from ..tl import TLMessage, MessageContainer, GzipPacked
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
    def __init__(self, session):
        self.session = session
        self._connection = ConnectionTcpFull()
        self._user_connected = False

        # Send and receive calls must be atomic
        self._send_lock = asyncio.Lock()
        self._recv_lock = asyncio.Lock()

        # We need to join the loops upon disconnection
        self._send_loop_handle = None
        self._recv_loop_handle = None

        # Sending something shouldn't block
        self._send_queue = asyncio.Queue()

        # Telegram responds to messages out of order. Keep
        # {id: Message} to set their Future result upon arrival.
        self._pending_messages = {}

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
        async with self._send_lock:
            await self._connection.connect(ip, port)
        self._user_connected = True
        self._send_loop_handle = asyncio.ensure_future(self._send_loop())
        self._recv_loop_handle = asyncio.ensure_future(self._recv_loop())

    async def disconnect(self):
        self._user_connected = False
        try:
            async with self._send_lock:
                await self._connection.close()
        except:
            __log__.exception('Ignoring exception upon disconnection')
        finally:
            self._send_loop_handle.cancel()
            self._recv_loop_handle.cancel()

    async def send(self, request):
        # TODO Should the asyncio.Future creation belong here?
        request.result = asyncio.Future()
        message = TLMessage(self.session, request)
        self._pending_messages[message.msg_id] = message
        await self._send_queue.put(message)

    # Loops

    async def _send_loop(self):
        while self._user_connected:
            # TODO If there's more than one item, send them all at once
            body = helpers.pack_message(
                self.session, await self._send_queue.get())

            # TODO Handle exceptions
            async with self._send_lock:
                await self._connection.send(body)

    async def _recv_loop(self):
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
        self._pending_ack.add(msg_id)
        code = reader.read_int(signed=False)
        reader.seek(-4)
        handler = self._handlers.get(code)
        if handler:
            await handler(msg_id, seq, reader)
        else:
            pass  # TODO Process updates and their entities

    async def _handle_rpc_result(self, msg_id, seq, reader):
        # TODO Don't make this a special case
        reader.read_int(signed=False)  # code
        message_id = reader.read_long()
        inner_code = reader.read_int(signed=False)
        reader.seek(-4)

        message = self._pending_messages.pop(message_id)
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

            # TODO Acknowledge that we received the error request_id
            # TODO Set message.request exception
        elif message:
            # TODO Make on_response result.set_result() instead replacing it
            if inner_code == GzipPacked.CONSTRUCTOR_ID:
                with BinaryReader(GzipPacked.read(reader)) as compressed_reader:
                    message.on_response(compressed_reader)
            else:
                message.on_response(reader)

            # TODO Process possible entities

        # TODO Try reading an object

    async def _handle_container(self, msg_id, seq, reader):
        for inner_msg_id, _, inner_len in MessageContainer.iter_read(reader):
            next_position = reader.tell_position() + inner_len
            await self._process_message(inner_msg_id, seq, reader)
            reader.set_position(next_position)  # Ensure reading correctly

    async def _handle_gzip_packed(self, msg_id, seq, reader):
        raise NotImplementedError

    async def _handle_pong(self, msg_id, seq, reader):
        raise NotImplementedError

    async def _handle_bad_server_salt(self, msg_id, seq, reader):
        bad_salt = reader.tgread_object()
        self.session.salt = bad_salt.new_server_salt
        self.session.save()

        # "the bad_server_salt response is received with the
        # correct salt, and the message is to be re-sent with it"
        await self._send_queue.put(self._pending_messages[bad_salt.bad_msg_id])

    async def _handle_bad_notification(self, msg_id, seq, reader):
        raise NotImplementedError

    async def _handle_detailed_info(self, msg_id, seq, reader):
        raise NotImplementedError

    async def _handle_new_detailed_info(self, msg_id, seq, reader):
        raise NotImplementedError

    async def _handle_new_session_created(self, msg_id, seq, reader):
        # TODO https://goo.gl/LMyN7A
        new_session = reader.tgread_object()
        self.session.salt = new_session.server_salt

    async def _handle_ack(self, msg_id, seq, reader):
        # Ignore every ack request *unless* when logging out, when it's
        # when it seems to only make sense. We also need to set a non-None
        # result since Telegram doesn't send the response for these.
        for msg_id in reader.tgread_object().msg_ids:
            # TODO pop msg_id if of type LogOutRequest, and confirm it
            pass

        return True

    async def _handle_future_salts(self, msg_id, seq, reader):
        raise NotImplementedError
