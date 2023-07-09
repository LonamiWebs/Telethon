import struct

from .abcs import Transport


class Intermediate(Transport):
    __slots__ = ("_init",)

    """
    Implementation of the [intermediate transport]:

    ```text
    +----+----...----+
    | len|  payload  |
    +----+----...----+
     ^^^^ 4 bytes
    ```

    [intermediate transport]: https://core.telegram.org/mtproto/mtproto-transports#intermediate
    """

    def __init__(self) -> None:
        self._init = False

    def pack(self, input: bytes, output: bytearray) -> None:
        assert len(input) % 4 == 0

        if not self._init:
            output += b"\xee\xee\xee\xee"
            self._init = True

        output += struct.pack("<i", len(input))
        output += input

    def unpack(self, input: bytes, output: bytearray) -> None:
        if len(input) < 4:
            raise ValueError(f"missing bytes, expected: {4}, got: {len(input)}")

        length = struct.unpack_from("<i", input)[0]
        if len(input) < length:
            raise ValueError(f"missing bytes, expected: {length}, got: {len(input)}")

        output += memoryview(input)[4 : 4 + length]
