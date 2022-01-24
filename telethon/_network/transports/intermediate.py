from .transport import Transport
import struct


class Intermediate(Transport):
    def __init__(self):
        self._init = False

    def recreate_fresh(self):
        return type(self)()

    def pack(self, input: bytes) -> bytes:
        if self._init:
            header = b''
        else:
            header = b'\xee\xee\xee\xee'
            self._init = True

        return header + struct.pack('<i', len(data)) + data

    def unpack(self, input: bytes) -> (int, bytes):
        if len(input) < 4:
            raise EOFError()

        length = struct.unpack('<i', input[:4])[0] + 4
        if len(input) < length:
            raise EOFError()

        return length, input[4:length]
