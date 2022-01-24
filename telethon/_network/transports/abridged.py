from .transport import Transport
import struct


class Abridged(Transport):
    def __init__(self):
        self._init = False

    def recreate_fresh(self):
        return type(self)()

    def pack(self, input: bytes) -> bytes:
        if self._init:
            header = b''
        else:
            header = b'\xef'
            self._init = True

        length = len(data) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        return header + length + data

    def unpack(self, input: bytes) -> (int, bytes):
        if len(input) < 4:
            raise EOFError()

        length = input[0]
        if length < 127:
            offset = 1
        else:
            offset = 4
            length = struct.unpack('<i', input[1:4] + b'\0')[0]

        length = (length << 2) + offset

        if len(input) < length:
            raise EOFError()

        return length, input[offset:length]
