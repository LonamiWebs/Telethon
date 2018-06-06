import asyncio
import logging

from .connection import ConnectionTcpFull
from .. import helpers
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
        self._user_connected = True
        async with self._send_lock:
            await self._connection.connect(ip, port)

    async def disconnect(self):
        self._user_connected = False
        try:
            async with self._send_lock:
                await self._connection.close()
        except:
            __log__.exception('Ignoring exception upon disconnection')

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

            self._pending_ack.add(remote_msg_id)

            with BinaryReader(message) as reader:
                code = reader.read_int(signed=False)
                reader.seek(-4)
                handler = self._handlers.get(code)
                if handler:
                    handler(remote_msg_id, remote_seq, reader)
                else:
                    pass  # TODO Process updates

    # Response Handlers

    def _handle_rpc_result(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_container(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_gzip_packed(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_pong(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_bad_server_salt(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_bad_notification(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_detailed_info(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_new_detailed_info(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_new_session_created(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_ack(self, msg_id, seq, reader):
        raise NotImplementedError

    def _handle_future_salts(self, msg_id, seq, reader):
        raise NotImplementedError
