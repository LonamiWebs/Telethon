from pytest import raises
from telethon._impl.mtproto import Intermediate


class Output(bytearray):
    __slots__ = ()

    def __call__(self, data: bytes | bytearray | memoryview) -> None:
        self += data


def setup_pack(n: int) -> tuple[Intermediate, bytes, Output]:
    input = bytes(x & 0xFF for x in range(n))
    return Intermediate(), input, Output()


def test_pack_empty() -> None:
    transport, input, output = setup_pack(0)
    transport.pack(input, output)
    assert output == b"\xee\xee\xee\xee\0\0\0\0"


def test_pack_non_padded() -> None:
    transport, input, output = setup_pack(7)
    with raises(AssertionError):
        transport.pack(input, output)


def test_pack_normal() -> None:
    transport, input, output = setup_pack(128)
    transport.pack(input, output)
    assert output[:8] == b"\xee\xee\xee\xee\x80\0\0\0"
    assert output[8:] == input


def test_unpack_small() -> None:
    transport = Intermediate()
    input = b"\x01"
    output = bytearray()
    with raises(ValueError) as e:
        transport.unpack(input, output)
    e.match("missing bytes")


def test_unpack_normal() -> None:
    transport, input, packed = setup_pack(128)
    unpacked = bytearray()
    transport.pack(input, packed)
    transport.unpack(packed[4:], unpacked)
    assert input == unpacked


def test_unpack_two_at_once() -> None:
    transport, input, packed = setup_pack(128)
    unpacked = bytearray()
    transport.pack(input, packed)
    n = transport.unpack(packed[4:] + packed[4:], unpacked)
    assert input == unpacked
    assert n == len(packed[4:])
