from .transport import Transport
import struct
from zlib import crc32


class Full(Transport):
    def __init__(self):
        self._send_counter = 0
        self._recv_counter = 0

    def recreate_fresh(self):
        return type(self)()

    def pack(self, input: bytes) -> bytes:
        # https://core.telegram.org/mtproto#tcp-transport
        length = len(input) + 12
        data = struct.pack('<ii', length, self._send_counter) + input
        crc = struct.pack('<I', crc32(data))
        self._send_counter += 1
        return data + crc

    def unpack(self, input: bytes) -> (int, bytes):
        if len(input) < 12:
            raise EOFError()

        length, seq = struct.unpack('<ii', input[:8])
        if len(input) < length:
            raise EOFError()

        if seq != self._recv_counter:
            raise ValueError(f'expected sequence value {self._recv_counter!r}, got {seq!r}')

        body = input[8:length - 4]
        checksum = struct.unpack('<I', input[length - 4:length])[0]

        valid_checksum = crc32(input[:length - 4])
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        self._recv_counter += 1
        return length, body
