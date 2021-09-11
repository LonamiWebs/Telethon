import struct
from zlib import crc32

from .connection import Connection, PacketCodec
from ...errors import InvalidChecksumError


class FullPacketCodec(PacketCodec):
    tag = None

    def __init__(self, connection):
        super().__init__(connection)
        self._send_counter = 0  # Important or Telegram won't reply

    def encode_packet(self, data):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        length = len(data) + 12
        data = struct.pack('<ii', length, self._send_counter) + data
        crc = struct.pack('<I', crc32(data))
        self._send_counter += 1
        return data + crc

    async def read_packet(self, reader):
        packet_len_seq = await reader.readexactly(8)  # 4 and 4
        packet_len, seq = struct.unpack('<ii', packet_len_seq)
        body = await reader.readexactly(packet_len - 8)
        checksum = struct.unpack('<I', body[-4:])[0]
        body = body[:-4]

        valid_checksum = crc32(packet_len_seq + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body


class ConnectionTcpFull(Connection):
    """
    Default Telegram mode. Sends 12 additional bytes and
    needs to calculate the CRC value of the packet itself.
    """
    packet_codec = FullPacketCodec
