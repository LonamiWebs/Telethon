from pytest import mark

from telethon._impl.tl.core import serialize_bytes_to


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
    expected = prefix + string.encode("ascii") + suffix
    buffer = bytearray()
    serialize_bytes_to(buffer, string.encode("ascii"))
    assert bytes(buffer) == expected
