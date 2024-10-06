import struct

from .abcs import BadStatusError, MissingBytesError, OutFn, Transport


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

    def pack(self, input: bytes, write: OutFn) -> None:
        assert len(input) % 4 == 0

        if not self._init:
            write(b"\xef")
            self._init = True

        length = len(input) // 4
        if length < 127:
            write(struct.pack("<b", length))
        else:
            write(struct.pack("<i", 0x7F | (length << 8)))
        write(input)

    def unpack(self, input: bytes | bytearray | memoryview, output: bytearray) -> int:
        if not input:
            raise MissingBytesError(expected=1, got=0)

        length = input[0]
        if 1 < length < 127:
            header_len = 1
        elif len(input) < 4:
            raise MissingBytesError(expected=4, got=len(input))
        else:
            header_len = 4
            length = struct.unpack_from("<i", input)[0] >> 8

        if length <= 0:
            if length < 0:
                raise BadStatusError(status=-length)
            raise ValueError(f"bad length, expected > 0, got: {length}")

        length *= 4
        if len(input) < header_len + length:
            raise MissingBytesError(expected=header_len + length, got=len(input))

        output += memoryview(input)[header_len : header_len + length]
        return header_len + length
