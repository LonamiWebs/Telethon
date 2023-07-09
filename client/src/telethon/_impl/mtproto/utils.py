import gzip
import struct
from typing import Optional

from ..tl.mtproto.types import GzipPacked, Message

DEFAULT_COMPRESSION_THRESHOLD: Optional[int] = 512
CONTAINER_SIZE_OVERHEAD = 4 + 4  # constructor_id, inner vec length
CONTAINER_MAX_SIZE = 1_044_456 - CONTAINER_SIZE_OVERHEAD
CONTAINER_MAX_LENGTH = 100
MESSAGE_SIZE_OVERHEAD = 8 + 4 + 4  # msg_id, seq_no, bytes


def check_message_buffer(message: bytes) -> None:
    if len(message) == 4:
        neg_http_code = struct.unpack("<i", message)[0]
        raise ValueError(f"transport error: {neg_http_code}")
    elif len(message) < 20:
        raise ValueError(
            f"server payload is too small to be a valid message: {message.hex()}"
        )


# https://core.telegram.org/mtproto/description#content-related-message
def message_requires_ack(message: Message) -> bool:
    return message.seqno % 2 == 1


def gzip_decompress(gzip_packed: GzipPacked) -> bytes:
    return gzip.decompress(gzip_packed.packed_data)


def gzip_compress(unpacked_data: bytes) -> bytes:
    return gzip.compress(unpacked_data)
