import struct
from zlib import crc32

from .abcs import BadStatus, MissingBytes, OutFn, Transport


class Full(Transport):
    __slots__ = ("_send_seq", "_recv_seq")

    """
    Implementation of the [full transport]:

    ```text
    +----+----+----...----+----+
    | len| seq|  payload  | crc|
    +----+----+----...----+----+
     ^^^^ 4 bytes
    ```

    [full transport]: https://core.telegram.org/mtproto/mtproto-transports#full
    """

    def __init__(self) -> None:
        self._send_seq = 0
        self._recv_seq = 0

    def pack(self, input: bytes, write: OutFn) -> None:
        assert len(input) % 4 == 0

        length = len(input) + 12
        # Unfortunately there's no hasher that can be updated multiple times,
        # so a temporary buffer must be used to hash it all in one go.
        tmp = struct.pack("<ii", length, self._send_seq) + input
        write(tmp)
        write(struct.pack("<I", crc32(tmp)))
        self._send_seq += 1

    def unpack(self, input: bytes | bytearray | memoryview, output: bytearray) -> int:
        if len(input) < 4:
            raise MissingBytes(expected=4, got=len(input))

        length = struct.unpack_from("<i", input)[0]
        assert isinstance(length, int)
        if length < 12:
            if length < 0:
                raise BadStatus(status=-length)
            raise ValueError(f"bad length, expected > 12, got: {length}")

        if len(input) < length:
            raise MissingBytes(expected=length, got=len(input))

        seq = struct.unpack_from("<i", input, 4)[0]
        if seq != self._recv_seq:
            raise ValueError(f"bad seq, expected: {self._recv_seq}, got: {seq}")

        crc = struct.unpack_from("<I", input, length - 4)[0]
        valid_crc = crc32(memoryview(input)[: length - 4])
        if crc != valid_crc:
            raise ValueError(f"bad crc, expected: {valid_crc}, got: {crc}")

        self._recv_seq += 1
        output += memoryview(input)[8 : length - 4]
        return length
