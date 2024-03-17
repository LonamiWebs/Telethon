from pytest import raises
from telethon._impl.mtproto import Full


class Output(bytearray):
    __slots__ = ()

    def __call__(self, data: bytes | bytearray | memoryview) -> None:
        self += data


def setup_pack(n: int) -> tuple[Full, bytes, Output]:
    input = bytes(x & 0xFF for x in range(n))
    return Full(), input, Output()


def setup_unpack(n: int) -> tuple[bytes, Full, bytes, bytearray]:
    transport, expected_output, input = setup_pack(n)
    transport.pack(expected_output, input)

    return expected_output, Full(), bytes(input), bytearray()


def test_pack_empty() -> None:
    transport, input, output = setup_pack(0)
    transport.pack(input, output)

    assert output == b"\x0c\x00\x00\x00\x00\x00\x00\x00&\xca\x8d2"


def test_pack_non_padded() -> None:
    transport, input, output = setup_pack(7)
    with raises(AssertionError):
        transport.pack(input, output)


def test_pack_normal() -> None:
    transport, input, output = setup_pack(128)
    transport.pack(input, output)

    assert output[:4] == b"\x8c\0\0\0"
    assert output[4:8] == b"\0\0\0\0"
    assert output[8 : 8 + len(input)] == input
    assert output[8 + len(input) :] == b"\x86s\x957"


def test_pack_twice() -> None:
    transport, input, output = setup_pack(128)
    transport.pack(input, output)
    output.clear()
    transport.pack(input, output)

    assert output[:4] == b"\x8c\0\0\0"
    assert output[4:8] == b"\x01\0\0\0"
    assert output[8 : 8 + len(input)] == input
    assert output[8 + len(input) :] == b"\x96\t\xf0J"


def test_unpack_small() -> None:
    transport = Full()
    input = b"\0\x01\x02"
    output = bytearray()
    with raises(ValueError) as e:
        transport.unpack(input, output)
    e.match("missing bytes")


def test_unpack_normal() -> None:
    expected_output, transport, input, output = setup_unpack(128)
    transport.unpack(input, output)
    assert output == expected_output


def test_unpack_two_at_once() -> None:
    expected_output, transport, input, output = setup_unpack(128)
    n = transport.unpack(input + input, output)
    assert output == expected_output
    assert n == len(input)
    with raises(ValueError) as e:
        transport.unpack(input, output)
    e.match("bad seq")


def test_unpack_twice() -> None:
    transport, input, packed = setup_pack(128)
    unpacked = bytearray()
    transport.pack(input, packed)
    transport.unpack(packed, unpacked)
    assert input == unpacked

    packed.clear()
    unpacked.clear()
    transport.pack(input, packed)
    transport.unpack(packed, unpacked)
    assert input == unpacked


def test_unpack_bad_crc() -> None:
    _, transport, input, output = setup_unpack(128)
    input = input[:-1] + bytes((input[-1] ^ 0xFF,))
    with raises(ValueError) as e:
        transport.unpack(input, output)
    e.match("bad crc")
    e.match("expected: 932541318")
    e.match("got: 3365237638")


def test_unpack_bad_seq() -> None:
    transport, input, packed = setup_pack(128)
    unpacked = bytearray()
    transport.pack(input, packed)
    packed.clear()
    transport.pack(input, packed)
    with raises(ValueError) as e:
        transport.unpack(packed, unpacked)
    e.match("bad seq")
    e.match("expected: 0")
    e.match("got: 1")
