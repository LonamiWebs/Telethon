import logging
import os
import struct
import time
from typing import Dict, List, Optional, Tuple, Type, Union

from ...crypto import AuthKey, decrypt_data_v2, encrypt_data_v2
from ...tl.core import Reader
from ...tl.mtproto.abcs import BadMsgNotification as AbcBadMsgNotification
from ...tl.mtproto.abcs import DestroySessionRes
from ...tl.mtproto.abcs import MsgDetailedInfo as AbcMsgDetailedInfo
from ...tl.mtproto.functions import get_future_salts
from ...tl.mtproto.types import (
    BadMsgNotification,
    BadServerSalt,
    DestroySessionNone,
    DestroySessionOk,
    FutureSalt,
    FutureSalts,
    GzipPacked,
    HttpWait,
    Message,
    MsgContainer,
    MsgDetailedInfo,
    MsgNewDetailedInfo,
    MsgResendReq,
    MsgsAck,
    MsgsAllInfo,
    MsgsStateInfo,
    MsgsStateReq,
    NewSessionCreated,
    Pong,
    RpcAnswerDropped,
    RpcAnswerDroppedRunning,
    RpcAnswerUnknown,
)
from ...tl.mtproto.types import RpcError as GeneratedRpcError
from ...tl.mtproto.types import RpcResult as GeneratedRpcResult
from ...tl.types import (
    Updates,
    UpdatesCombined,
    UpdateShort,
    UpdateShortChatMessage,
    UpdateShortMessage,
    UpdateShortSentMessage,
    UpdatesTooLong,
)
from ..utils import (
    CONTAINER_MAX_LENGTH,
    CONTAINER_MAX_SIZE,
    DEFAULT_COMPRESSION_THRESHOLD,
    MESSAGE_SIZE_OVERHEAD,
    check_message_buffer,
    gzip_compress,
    gzip_decompress,
    message_requires_ack,
)
from .types import BadMessage, Deserialization, MsgId, Mtp, RpcError, RpcResult

NUM_FUTURE_SALTS = 64

SALT_USE_DELAY = 60

UPDATE_IDS = {
    Updates.constructor_id(),
    UpdatesCombined.constructor_id(),
    UpdateShort.constructor_id(),
    UpdateShortChatMessage.constructor_id(),
    UpdateShortMessage.constructor_id(),
    UpdateShortSentMessage.constructor_id(),
    UpdatesTooLong.constructor_id(),
}

HEADER_LEN = 8 + 8  # salt, client_id

CONTAINER_HEADER_LEN = (8 + 4 + 4) + (4 + 4)  # msg_id, seq_no, size, constructor, len


class Single:
    """
    Sentinel value.
    """


class Pending:
    """
    Sentinel value.
    """


class Encrypted(Mtp):
    def __init__(
        self,
        auth_key: AuthKey,
        *,
        time_offset: Optional[int] = None,
        first_salt: Optional[int] = None,
        compression_threshold: Optional[int] = DEFAULT_COMPRESSION_THRESHOLD,
    ) -> None:
        self._auth_key = auth_key
        self._time_offset: int = time_offset or 0
        self._salts: List[FutureSalt] = [
            FutureSalt(valid_since=0, valid_until=0x7FFFFFFF, salt=first_salt or 0)
        ]
        self._start_salt_time: Optional[Tuple[int, float]] = None
        self._compression_threshold = compression_threshold
        self._rpc_results: List[Tuple[MsgId, RpcResult]] = []
        self._updates: List[bytes] = []
        self._buffer = bytearray()
        self._salt_request_msg_id: Optional[int] = None

        self._handlers = {
            GeneratedRpcResult.constructor_id(): self._handle_rpc_result,
            MsgsAck.constructor_id(): self._handle_ack,
            BadMsgNotification.constructor_id(): self._handle_bad_notification,
            BadServerSalt.constructor_id(): self._handle_bad_notification,
            MsgsStateReq.constructor_id(): self._handle_state_req,
            MsgsStateInfo.constructor_id(): self._handle_state_info,
            MsgsAllInfo.constructor_id(): self._handle_msg_all,
            MsgDetailedInfo.constructor_id(): self._handle_detailed_info,
            MsgNewDetailedInfo.constructor_id(): self._handle_detailed_info,
            MsgResendReq.constructor_id(): self._handle_msg_resend,
            FutureSalt.constructor_id(): self._handle_future_salt,
            FutureSalts.constructor_id(): self._handle_future_salts,
            Pong.constructor_id(): self._handle_pong,
            DestroySessionOk.constructor_id(): self._handle_destroy_session,
            DestroySessionNone.constructor_id(): self._handle_destroy_session,
            NewSessionCreated.constructor_id(): self._handle_new_session_created,
            MsgContainer.constructor_id(): self._handle_container,
            GzipPacked.constructor_id(): self._handle_gzip_packed,
            HttpWait.constructor_id(): self._handle_http_wait,
        }

        self._client_id: int
        self._sequence: int
        self._last_msg_id: int
        self._in_pending_ack: List[int] = []
        self._out_pending_ack: Dict[
            int, Union[int, Type[Single], Type[Pending]]  # msg_id: container_id
        ] = {}
        self._msg_count: int
        self._reset_session()

    @property
    def auth_key(self) -> bytes:
        return self._auth_key.data

    def _correct_time_offset(self, msg_id: int) -> None:
        now = time.time()
        correct = msg_id >> 32
        self._time_offset = correct - int(now)
        self._last_msg_id = 0

    def _adjusted_now(self) -> float:
        return time.time() + self._time_offset

    def _reset_session(self) -> None:
        self._client_id = struct.unpack("<q", os.urandom(8))[0]
        self._sequence = 0
        self._last_msg_id = 0
        self._in_pending_ack.clear()
        self._out_pending_ack.clear()
        self._msg_count = 0

    def _get_new_msg_id(self) -> int:
        new_msg_id = int(self._adjusted_now() * 0x100000000)
        if self._last_msg_id >= new_msg_id:
            new_msg_id = self._last_msg_id + 4

        self._last_msg_id = new_msg_id
        return new_msg_id

    def _get_seq_no(self, content_related: bool) -> int:
        if content_related:
            self._sequence += 2
            return self._sequence - 1
        else:
            return self._sequence

    def _serialize_msg(self, body: bytes, content_related: bool) -> MsgId:
        if not self._buffer:
            # Reserve space for `finalize`
            self._buffer += bytes(HEADER_LEN + CONTAINER_HEADER_LEN)

        msg_id = self._get_new_msg_id()
        seq_no = self._get_seq_no(content_related)
        self._buffer += struct.pack("<qii", msg_id, seq_no, len(body))
        self._buffer += body
        self._msg_count += 1

        if content_related:
            self._out_pending_ack[msg_id] = Pending

        return MsgId(msg_id)

    def _get_current_salt(self) -> int:
        return self._salts[-1].salt if self._salts else 0

    def _finalize_plain(self) -> bytes:
        if not self._msg_count:
            return b""

        if self._msg_count == 1:
            del self._buffer[:CONTAINER_HEADER_LEN]

        self._buffer[:HEADER_LEN] = struct.pack(
            "<qq", self._get_current_salt(), self._client_id
        )

        if self._msg_count == 1:
            container_msg_id: Union[Type[Single], int] = Single
        else:
            container_msg_id = self._get_new_msg_id()
            self._buffer[HEADER_LEN : HEADER_LEN + CONTAINER_HEADER_LEN] = struct.pack(
                "<qiiIi",
                container_msg_id,
                self._get_seq_no(False),
                len(self._buffer) - HEADER_LEN - CONTAINER_HEADER_LEN + 8,
                MsgContainer.constructor_id(),
                self._msg_count,
            )

        for m, c in self._out_pending_ack.items():
            if c is Pending:
                self._out_pending_ack[m] = container_msg_id

        self._msg_count = 0
        result = bytes(self._buffer)
        self._buffer.clear()
        return result

    def _process_message(self, message: Message) -> None:
        if message_requires_ack(message):
            self._in_pending_ack.append(message.msg_id)

        # https://core.telegram.org/mtproto/service_messages
        # https://core.telegram.org/mtproto/service_messages_about_messages
        constructor_id = struct.unpack_from("<I", message.body)[0]
        self._handlers.get(constructor_id, self._handle_update)(message)

        assert len(self._out_pending_ack) < 1000

    def _handle_rpc_result(self, message: Message) -> None:
        rpc_result = GeneratedRpcResult.from_bytes(message.body)
        req_msg_id = rpc_result.req_msg_id
        result = rpc_result.result

        del self._out_pending_ack[req_msg_id]

        msg_id = MsgId(req_msg_id)
        inner_constructor = struct.unpack_from("<I", result)[0]

        if inner_constructor == GeneratedRpcError.constructor_id():
            self._rpc_results.append(
                (
                    msg_id,
                    RpcError._from_mtproto_error(GeneratedRpcError.from_bytes(result)),
                )
            )
        elif inner_constructor == RpcAnswerUnknown.constructor_id():
            pass  # msg_id = rpc_drop_answer.msg_id
        elif inner_constructor == RpcAnswerDroppedRunning.constructor_id():
            pass  # msg_id = rpc_drop_answer.msg_id, original_request.msg_id
        elif inner_constructor == RpcAnswerDropped.constructor_id():
            pass  # dropped
        elif inner_constructor == GzipPacked.constructor_id():
            body = gzip_decompress(GzipPacked.from_bytes(result))
            self._store_own_updates(body)
            self._rpc_results.append((msg_id, body))
        else:
            self._store_own_updates(result)
            self._rpc_results.append((msg_id, result))

    def _store_own_updates(self, body: bytes) -> None:
        constructor_id = struct.unpack_from("I", body)[0]
        if constructor_id in UPDATE_IDS:
            self._updates.append(body)

    def _handle_ack(self, message: Message) -> None:
        if __debug__:
            msgs_ack = MsgsAck.from_bytes(message.body)
            for msg_id in msgs_ack.msg_ids:
                assert msg_id in self._out_pending_ack

    def _handle_bad_notification(self, message: Message) -> None:
        bad_msg = AbcBadMsgNotification.from_bytes(message.body)
        assert isinstance(bad_msg, (BadServerSalt, BadMsgNotification))

        exc = BadMessage(code=bad_msg.error_code)

        bad_msg_id = bad_msg.bad_msg_id
        if bad_msg_id in self._out_pending_ack:
            bad_msg_ids = [bad_msg.bad_msg_id]
        else:
            # Search bad_msg_id in containers instead.
            bad_msg_ids = [
                m for m, c in self._out_pending_ack.items() if bad_msg_id == c
            ]
            if not bad_msg_ids:
                raise KeyError(f"bad_msg for unknown msg_id: {bad_msg_id}")

        for bad_msg_id in bad_msg_ids:
            if bad_msg_id == self._salt_request_msg_id:
                # Response to internal request, do not propagate.
                self._salt_request_msg_id = None
            else:
                self._rpc_results.append((MsgId(bad_msg_id), exc))
            del self._out_pending_ack[bad_msg_id]

        if isinstance(bad_msg, BadServerSalt) and self._get_current_salt() == 0:
            # If we had no valid salt, this error is expected.
            exc.severity = logging.INFO

        if isinstance(bad_msg, BadServerSalt):
            self._salts.clear()
            self._salts.append(
                FutureSalt(
                    valid_since=0, valid_until=0x7FFFFFFF, salt=bad_msg.new_server_salt
                )
            )
            self._salt_request_msg_id = None
        elif bad_msg.error_code in (16, 17):
            self._correct_time_offset(message.msg_id)
        elif bad_msg.error_code in (32, 33):
            self._reset_session()
        else:
            raise exc

    def _handle_state_req(self, message: Message) -> None:
        MsgsStateReq.from_bytes(message.body)

    def _handle_state_info(self, message: Message) -> None:
        MsgsStateInfo.from_bytes(message.body)

    def _handle_msg_all(self, message: Message) -> None:
        MsgsAllInfo.from_bytes(message.body)

    def _handle_detailed_info(self, message: Message) -> None:
        msg_detailed = AbcMsgDetailedInfo.from_bytes(message.body)
        if isinstance(msg_detailed, MsgDetailedInfo):
            self._in_pending_ack.append(msg_detailed.answer_msg_id)
        elif isinstance(msg_detailed, MsgNewDetailedInfo):
            self._in_pending_ack.append(msg_detailed.answer_msg_id)
        else:
            assert False

    def _handle_msg_resend(self, message: Message) -> None:
        MsgResendReq.from_bytes(message.body)

    def _handle_future_salts(self, message: Message) -> None:
        salts = FutureSalts.from_bytes(message.body)
        del self._out_pending_ack[salts.req_msg_id]

        if salts.req_msg_id == self._salt_request_msg_id:
            # Response to internal request, do not propagate.
            self._salt_request_msg_id = None
        else:
            self._rpc_results.append((MsgId(salts.req_msg_id), message.body))

        self._start_salt_time = (salts.now, self._adjusted_now())
        self._salts = salts.salts
        self._salts.sort(key=lambda salt: -salt.valid_since)

    def _handle_future_salt(self, message: Message) -> None:
        FutureSalt.from_bytes(message.body)
        assert False  # no request should cause this

    def _handle_pong(self, message: Message) -> None:
        pong = Pong.from_bytes(message.body)
        self._rpc_results.append((MsgId(pong.msg_id), message.body))

    def _handle_destroy_session(self, message: Message) -> None:
        DestroySessionRes.from_bytes(message.body)

    def _handle_new_session_created(self, message: Message) -> None:
        new_session = NewSessionCreated.from_bytes(message.body)
        self._salts.clear()
        self._salts.append(
            FutureSalt(
                valid_since=0, valid_until=0x7FFFFFFF, salt=new_session.server_salt
            )
        )

    def _handle_container(self, message: Message) -> None:
        container = MsgContainer.from_bytes(message.body)
        for inner_message in container.messages:
            self._process_message(inner_message)

    def _handle_gzip_packed(self, message: Message) -> None:
        container = GzipPacked.from_bytes(message.body)
        inner_body = gzip_decompress(container)
        self._process_message(
            Message(
                msg_id=message.msg_id,
                seqno=message.seqno,
                bytes=len(inner_body),
                body=inner_body,
            )
        )

    def _handle_http_wait(self, message: Message) -> None:
        HttpWait.from_bytes(message.body)

    def _handle_update(self, message: Message) -> None:
        self._updates.append(message.body)

    def _try_request_salts(self) -> None:
        if (
            len(self._salts) == 1
            and self._salt_request_msg_id is None
            and self._get_current_salt() != 0
        ):
            # If salts are requested in a container leading to bad_msg,
            # the bad_msg_id will refer to the container, not the salts request.
            #
            # We don't keep track of containers and content-related messages they contain for simplicity.
            # This would break, because we couldn't identify the response.
            #
            # So salts are only requested once we have a valid salt to reduce the chances of this happening.
            self._salt_request_msg_id = self._serialize_msg(
                bytes(get_future_salts(num=NUM_FUTURE_SALTS)), True
            )

    def push(self, request: bytes) -> Optional[MsgId]:
        if self._start_salt_time and len(self._salts) >= 2:
            start_secs, start_instant = self._start_salt_time
            salt = self._salts[-2]
            now = start_secs + (start_instant - self._adjusted_now())
            if now >= salt.valid_since + SALT_USE_DELAY:
                self._salts.pop()

        self._try_request_salts()
        if self._salt_request_msg_id:
            # Don't add anything else to the container while we still need new salts.
            return None

        if self._in_pending_ack:
            self._serialize_msg(bytes(MsgsAck(msg_ids=self._in_pending_ack)), False)
            self._in_pending_ack = []

        if self._msg_count >= CONTAINER_MAX_LENGTH:
            return None

        assert len(request) + MESSAGE_SIZE_OVERHEAD <= CONTAINER_MAX_SIZE
        assert len(request) % 4 == 0

        body = request
        if self._compression_threshold is not None:
            if len(request) >= self._compression_threshold:
                compressed = bytes(GzipPacked(packed_data=gzip_compress(request)))
                if len(compressed) < len(request):
                    body = compressed

        new_size = len(self._buffer) + len(body) + MESSAGE_SIZE_OVERHEAD
        if new_size >= CONTAINER_MAX_SIZE:
            return None

        return self._serialize_msg(body, True)

    def finalize(self) -> bytes:
        buffer = self._finalize_plain()
        if not buffer:
            return buffer
        else:
            return encrypt_data_v2(buffer, self._auth_key)

    def deserialize(self, payload: bytes) -> Deserialization:
        check_message_buffer(payload)

        plaintext = decrypt_data_v2(payload, self._auth_key)

        _, client_id = struct.unpack_from("<qq", plaintext)  # salt, client_id
        if client_id != self._client_id:
            raise RuntimeError("wrong session id")

        self._process_message(Message._read_from(Reader(memoryview(plaintext)[16:])))

        result = Deserialization(rpc_results=self._rpc_results, updates=self._updates)
        self._rpc_results = []
        self._updates = []
        return result
