import struct
from typing import Optional

from ..utils import check_message_buffer
from .types import Deserialization, MsgId, Mtp


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

    def finalize(self) -> bytes:
        result = bytes(self._buffer)
        self._buffer.clear()
        return result

    def deserialize(self, payload: bytes) -> Deserialization:
        check_message_buffer(payload)

        auth_key_id, msg_id, length = struct.unpack_from("<qqi", payload)
        if auth_key_id != 0:
            raise ValueError(f"bad auth key, expected: 0, got: {auth_key_id}")

        # https://core.telegram.org/mtproto/description#message-identifier-msg-id
        if msg_id <= 0 or (msg_id % 4) != 1:
            raise ValueError(f"bad msg id, got: {msg_id}")

        if length < 0:
            raise ValueError(f"bad length: expected >= 0, got: {length}")

        if 20 + length > len(payload):
            raise ValueError(
                f"message too short, expected: {20 + length}, got {len(payload)}"
            )

        return Deserialization(
            rpc_results=[(MsgId(0), bytes(payload[20 : 20 + length]))], updates=[]
        )
