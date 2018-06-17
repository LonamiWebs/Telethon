import errno
import struct
from zlib import crc32

from .common import Connection
from ...errors import InvalidChecksumError
from ...extensions import TcpClient


class ConnectionTcpFull(Connection):
    """
    Default Telegram mode. Sends 12 additional bytes and
    needs to calculate the CRC value of the packet itself.
    """
    def __init__(self, *, loop, timeout, proxy=None):
        super().__init__(loop=loop, timeout=timeout, proxy=proxy)
        self._send_counter = 0
        self.conn = TcpClient(
            timeout=self._timeout, loop=self._loop, proxy=self._proxy
        )
        self.read = self.conn.read
        self.write = self.conn.write

    async def connect(self, ip, port):
        try:
            await self.conn.connect(ip, port)
        except OSError as e:
            if e.errno == errno.EISCONN:
                return  # Already connected, no need to re-set everything up
            else:
                raise

        self._send_counter = 0

    def get_timeout(self):
        return self.conn.timeout

    def is_connected(self):
        return self.conn.is_connected

    async def close(self):
        self.conn.close()

    async def recv(self):
        packet_len_seq = await self.read(8)  # 4 and 4
        packet_len, seq = struct.unpack('<ii', packet_len_seq)
        body = await self.read(packet_len - 8)
        checksum = struct.unpack('<I', body[-4:])[0]
        body = body[:-4]

        valid_checksum = crc32(packet_len_seq + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body

    async def send(self, message):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        length = len(message) + 12
        data = struct.pack('<ii', length, self._send_counter) + message
        crc = struct.pack('<I', crc32(data))
        self._send_counter += 1
        await self.write(data + crc)
