import struct

from .abcs import BadStatus, MissingBytes, OutFn, Transport


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

    def pack(self, input: bytes, write: OutFn) -> None:
        assert len(input) % 4 == 0

        if not self._init:
            write(b"\xee\xee\xee\xee")
            self._init = True

        write(struct.pack("<i", len(input)))
        write(input)

    def unpack(self, input: bytes | bytearray | memoryview, output: bytearray) -> int:
        if len(input) < 4:
            raise MissingBytes(expected=4, got=len(input))

        length = struct.unpack_from("<i", input)[0]
        assert isinstance(length, int)
        if len(input) < length:
            raise MissingBytes(expected=length, got=len(input))

        if length <= 4:
            if length >= 4 and (status := struct.unpack("<i", input[4 : 4 + length])[0]) < 0:
                raise BadStatus(status=-status)

            raise ValueError(f"bad length, expected > 0, got: {length}")

        output += memoryview(input)[4 : 4 + length]
        return length + 4
