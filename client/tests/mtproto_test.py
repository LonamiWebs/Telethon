import struct

from pytest import raises
from telethon._impl.crypto import AuthKey
from telethon._impl.mtproto import Encrypted, Plain, RpcError
from telethon._impl.tl.mtproto.types import RpcError as GeneratedRpcError


def test_rpc_error_parsing() -> None:
    assert RpcError.from_mtproto_error(
        GeneratedRpcError(
            error_code=400,
            error_message="CHAT_INVALID",
        )
    ) == RpcError(
        code=400,
        name="CHAT_INVALID",
        value=None,
        caused_by=None,
    )

    assert RpcError.from_mtproto_error(
        GeneratedRpcError(
            error_code=420,
            error_message="FLOOD_WAIT_31",
        )
    ) == RpcError(
        code=420,
        name="FLOOD_WAIT",
        value=31,
        caused_by=None,
    )

    assert RpcError.from_mtproto_error(
        GeneratedRpcError(
            error_code=500,
            error_message="INTERDC_2_CALL_ERROR",
        )
    ) == RpcError(
        code=500,
        name="INTERDC_CALL_ERROR",
        value=2,
        caused_by=None,
    )


PLAIN_REQUEST = b"Hey!"


def test_plain_finalize_clears_buffer() -> None:
    mtp = Plain()

    mtp.push(PLAIN_REQUEST)
    assert len(mtp.finalize()) == 24

    mtp.push(PLAIN_REQUEST)
    assert len(mtp.finalize()) == 24


def test_plain_only_one_push_allowed() -> None:
    mtp = Plain()

    assert mtp.push(PLAIN_REQUEST) is not None
    assert mtp.push(PLAIN_REQUEST) is None


MESSAGE_PREFIX_LEN = 8 + 8  # salt + client_id
GZIP_PACKED_HEADER = b"\xa1\xcf\x72\x30"
MSG_CONTAINER_HEADER = b"\xdc\xf8\xf1\x73"
REQUEST = b"Hey!"
REQUEST_B = b"Bye!"


def auth_key() -> AuthKey:
    return AuthKey.from_bytes(bytes(256))


def ensure_buffer_is_message(buffer: bytes, body: bytes, seq_no: int) -> None:
    # msg_id, based on time
    assert buffer[0:8] != bytes(8)
    # seq_no, sequential odd number
    assert buffer[8:12] == struct.pack("<i", seq_no)
    # bytes, body length
    assert buffer[12:16] == struct.pack("<i", len(body))
    # body
    assert buffer[16:] == body


def test_serialization_has_salt_client_id() -> None:
    mtp = Encrypted(auth_key())

    mtp.push(REQUEST)
    buffer = mtp._finalize_plain()

    # salt
    assert buffer[0:8] == bytes(8)
    # client_id
    assert buffer[8:16] != bytes(8)
    # message
    ensure_buffer_is_message(buffer[MESSAGE_PREFIX_LEN:], REQUEST, 1)


def test_correct_single_serialization() -> None:
    mtp = Encrypted(auth_key())

    assert mtp.push(REQUEST) is not None
    buffer = mtp._finalize_plain()

    ensure_buffer_is_message(buffer[MESSAGE_PREFIX_LEN:], REQUEST, 1)


def test_correct_multi_serialization() -> None:
    mtp = Encrypted(auth_key(), compression_threshold=None)

    assert mtp.push(REQUEST) is not None
    assert mtp.push(REQUEST_B) is not None
    buffer = mtp._finalize_plain()
    buffer = buffer[MESSAGE_PREFIX_LEN:]

    # container msg_id
    assert buffer[0:8] != bytes(8)
    # seq_no (after 1, 3 content-related comes 4)
    assert buffer[8:12] == b"\x04\0\0\0"
    # body length
    assert buffer[12:16] == b"\x30\0\0\0"

    # container constructor_id
    assert buffer[16:20] == MSG_CONTAINER_HEADER
    # message count
    assert buffer[20:24] == b"\x02\0\0\0"

    ensure_buffer_is_message(buffer[24:44], REQUEST, 1)
    ensure_buffer_is_message(buffer[44:], REQUEST_B, 3)


def test_correct_single_large_serialization() -> None:
    mtp = Encrypted(auth_key(), compression_threshold=None)
    data = bytes(0x7F for _ in range(768 * 1024))

    assert mtp.push(data) is not None
    buffer = mtp._finalize_plain()

    buffer = buffer[MESSAGE_PREFIX_LEN:]
    assert len(buffer) == 16 + len(data)


def test_correct_multi_large_serialization() -> None:
    mtp = Encrypted(auth_key(), compression_threshold=None)
    data = bytes(0x7F for _ in range(768 * 1024))

    assert mtp.push(data) is not None
    assert mtp.push(data) is None

    buffer = mtp._finalize_plain()
    buffer = buffer[MESSAGE_PREFIX_LEN:]
    assert len(buffer) == 16 + len(data)


def test_large_payload_panics() -> None:
    mtp = Encrypted(auth_key())

    with raises(AssertionError):
        mtp.push(bytes(2 * 1024 * 1024))


def test_non_padded_payload_panics() -> None:
    mtp = Encrypted(auth_key())

    with raises(AssertionError):
        mtp.push(b"\x01\x02\x03")


def test_no_compression_is_honored() -> None:
    mtp = Encrypted(auth_key(), compression_threshold=None)
    mtp.push(bytes(512 * 1024))
    buffer = mtp._finalize_plain()
    assert GZIP_PACKED_HEADER not in buffer


def test_some_compression() -> None:
    mtp = Encrypted(auth_key(), compression_threshold=768 * 1024)
    mtp.push(bytes(512 * 1024))
    buffer = mtp._finalize_plain()
    assert GZIP_PACKED_HEADER not in buffer

    mtp = Encrypted(auth_key(), compression_threshold=256 * 1024)
    mtp.push(bytes(512 * 1024))
    buffer = mtp._finalize_plain()
    assert GZIP_PACKED_HEADER in buffer

    mtp = Encrypted(auth_key())
    mtp.push(bytes(512 * 1024))
    buffer = mtp._finalize_plain()
    assert GZIP_PACKED_HEADER in buffer
