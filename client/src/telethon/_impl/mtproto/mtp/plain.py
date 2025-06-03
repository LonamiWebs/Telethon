import struct
from typing import Optional

from ..utils import check_message_buffer
from .types import (
    BadAuthKeyError,
    BadMsgIdError,
    Deserialization,
    MsgId,
    Mtp,
    NegativeLengthError,
    RpcResult,
    TooLongMsgError,
)


class Plain(Mtp):
    def __init__(self) -> None:
        self._buffer = bytearray()

    # https://core.telegram.org/mtproto/description#unencrypted-message
    def push(self, request: bytes) -> Optional[MsgId]:
        if self._buffer:
            return None

        # https://core.telegram.org/mtproto/samples-auth_key seems to
        # imply a need to generate a valid `message_id`, but 0 works too.
        msg_id = MsgId(0)

        # auth_key_id = 0, message_id, message_data_length.
        self._buffer += struct.pack("<qqi", 0, msg_id, len(request))
        self._buffer += request  # message_data
        return msg_id

    def finalize(self) -> Optional[tuple[MsgId, bytes]]:
        if not self._buffer:
            return None

        result = bytes(self._buffer)
        self._buffer.clear()
        return MsgId(0), result

    def deserialize(
        self, payload: bytes | bytearray | memoryview
    ) -> list[Deserialization]:
        check_message_buffer(payload)

        auth_key_id, msg_id, length = struct.unpack_from("<qqi", payload)
        if auth_key_id != 0:
            raise BadAuthKeyError(got=auth_key_id, expected=0)

        # https://core.telegram.org/mtproto/description#message-identifier-msg-id
        if msg_id <= 0 or (msg_id % 4) != 1:
            raise BadMsgIdError(got=msg_id)

        if length < 0:
            raise NegativeLengthError(got=length)

        if 20 + length > (lp := len(payload)):
            raise TooLongMsgError(got=length, max_length=lp - 20)

        return [RpcResult(MsgId(0), bytes(payload[20 : 20 + length]))]

    def reset(self) -> None:
        self._buffer.clear()
