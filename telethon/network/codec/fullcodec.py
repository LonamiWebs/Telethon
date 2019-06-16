import struct
import zlib

from .basecodec import BaseCodec
from ...errors import InvalidChecksumError


class FullCodec(BaseCodec):
    """
    Default Telegram codec. Sends 12 additional bytes and
    needs to calculate the CRC value of the packet itself.
    """
    def __init__(self):
        self._send_counter = 0  # Important or Telegram won't reply

    @staticmethod
    def header_length():
        return 8

    @staticmethod
    def tag():
        return None

    def encode_packet(self, data, ip, port):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        length = len(data) + 12
        data = struct.pack('<ii', length, self._send_counter) + data
        crc = struct.pack('<I', zlib.crc32(data))
        self._send_counter += 1
        return data + crc

    def decode_header(self, header):
        length, seq = struct.unpack('<ii', header)
        return length - 8

    def decode_body(self, header, body):
        checksum = struct.unpack('<I', body[-4:])[0]
        body = body[:-4]

        valid_checksum = zlib.crc32(header + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body
