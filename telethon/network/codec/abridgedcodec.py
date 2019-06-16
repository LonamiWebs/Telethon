import struct

from .basecodec import BaseCodec


class AbridgedCodec(BaseCodec):
    """
    This is the mode with the lowest overhead, as it will
    only require 1 byte if the packet length is less than
    508 bytes (127 << 2, which is very common).
    """
    @staticmethod
    def header_length():
        return 1

    @staticmethod
    def tag():
        return b'\xef'  # note: obfuscated tag is this 4 times

    def encode_packet(self, data, ip, port):
        length = len(data) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        return length + data

    def decode_header(self, header):
        if len(header) == 4:
            length = struct.unpack('<i', header[1:] + b'\0')[0]
        else:
            length = struct.unpack('<B', header)[0]
            if length >= 127:
                return -3  # needs 3 more bytes

        return length << 2
