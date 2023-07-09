import struct

from pytest import mark
from telethon._impl.tl.core import Reader
from telethon._impl.tl.core.serializable import Serializable
from telethon._impl.tl.mtproto.types import BadServerSalt
from telethon._impl.tl.types import GeoPoint


@mark.parametrize(
    ("string", "prefix", "suffix"),
    [
        ("", b"\00", b"\00\x00\x00"),
        ("Hi", b"\02", b"\00"),
        ("Hi!", b"\03", b""),
        ("Hello", b"\05", b"\00\x00"),
        ("Hello, world!", b"\x0d", b"\00\x00"),
        (
            "This is a very long string, and it has to be longer than 253 \
characters, which are quite a few but we can make it! Although, \
it is quite challenging. The quick brown fox jumps over the lazy \
fox. There is still some more text we need to type. Oh, this \
sentence made it past!",
            b"\xfe\x11\x01\x00",
            b"\x00\x00\x00",
        ),
    ],
)
def test_string(string: str, prefix: bytes, suffix: bytes) -> None:
    data = prefix + string.encode("ascii") + suffix
    assert str(Reader(data).read_bytes(), "ascii") == string


@mark.parametrize(
    "obj",
    [
        GeoPoint(long=12.34, lat=56.78, access_hash=123123, accuracy_radius=100),
        BadServerSalt(
            bad_msg_id=1234,
            bad_msg_seqno=5678,
            error_code=9876,
            new_server_salt=5432,
        ),
    ],
)
def test_generated_object(obj: Serializable) -> None:
    assert bytes(obj)[:4] == struct.pack("<I", obj.constructor_id())
    assert type(obj)._read_from(Reader(bytes(obj)[4:])) == obj
    assert Reader(bytes(obj)).read_serializable(type(obj)) == obj


def test_repeated_read() -> None:
    reader = Reader(bytes(range(8)))
    assert reader.read(4) == bytes(range(4))
    assert reader.read(4) == bytes(range(4, 8))

    reader = Reader(bytes(range(8)))
    assert reader.read_fmt("4b", 4) == tuple(range(4))
    assert reader.read_fmt("4b", 4) == tuple(range(4, 8))
