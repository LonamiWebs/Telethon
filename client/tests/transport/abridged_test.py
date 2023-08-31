from typing import Tuple

from pytest import raises
from telethon._impl.mtproto.transport.abridged import Abridged


class Output(bytearray):
    __slots__ = ()

    def __call__(self, data: bytes) -> None:
        self += data


def setup_pack(n: int) -> Tuple[Abridged, bytes, Output]:
    input = bytes(x & 0xFF for x in range(n))
    return Abridged(), input, Output()


def test_pack_empty() -> None:
    transport, input, output = setup_pack(0)
    transport.pack(input, output)
    assert output == b"\xef\0"


def test_pack_non_padded() -> None:
    transport, input, output = setup_pack(7)
    with raises(AssertionError):
        transport.pack(input, output)


def test_pack_normal() -> None:
    transport, input, output = setup_pack(128)
    transport.pack(input, output)
    assert output[:2] == b"\xef\x20"
    assert output[2:] == input


def pack_large() -> None:
    transport, input, output = setup_pack(1024)
    transport.pack(input, output)
    assert output[:5] == b"\xef\x7f\0\x01\0"
    assert output[5:] == input


def test_unpack_small() -> None:
    transport = Abridged()
    input = b"\x01"
    output = bytearray()
    with raises(ValueError) as e:
        transport.unpack(input, output)
    e.match("missing bytes")


def test_unpack_normal() -> None:
    transport, input, packed = setup_pack(128)
    unpacked = bytearray()
    transport.pack(input, packed)
    transport.unpack(packed[1:], unpacked)
    assert input == unpacked


def unpack_large() -> None:
    transport, input, packed = setup_pack(1024)
    unpacked = bytearray()
    transport.pack(input, packed)
    transport.unpack(packed[1:], unpacked)
    assert input == unpacked
