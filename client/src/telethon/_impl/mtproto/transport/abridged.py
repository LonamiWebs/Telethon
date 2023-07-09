import struct

from .abcs import Transport


class Abridged(Transport):
    __slots__ = ("_init",)

    """
    Implementation of the [abridged transport]:

    ```text
    +----+----...----+
    | len|  payload  |
    +----+----...----+
     ^^^^ 1 or 4 bytes
    ```

    [abridged transport]: https://core.telegram.org/mtproto/mtproto-transports#abridged
    """

    def __init__(self) -> None:
        self._init = False

    def pack(self, input: bytes, output: bytearray) -> None:
        assert len(input) % 4 == 0

        if not self._init:
            output += b"\xef"
            self._init = True

        length = len(input) // 4
        if length < 127:
            output += struct.pack("<b", length)
        else:
            output += struct.pack("<i", 0x7F | (length << 8))
        output += input

    def unpack(self, input: bytes, output: bytearray) -> None:
        if not input:
            raise ValueError("missing bytes, expected: 1, got: 0")

        length = input[0]
        if length < 127:
            header_len = 1
        elif len(input) < 4:
            raise ValueError(f"missing bytes, expected: 4, got: {len(input)}")
        else:
            header_len = 4
            length = struct.unpack_from("<i", input)[0] >> 8

        length *= 4
        if len(input) < header_len + length:
            raise ValueError(
                f"missing bytes, expected: {header_len + length}, got: {len(input)}"
            )

        output += memoryview(input)[header_len : header_len + length]
