import struct

from .tcpfull import ConnectionTcpFull


class ConnectionTcpAbridged(ConnectionTcpFull):
    """
    This is the mode with the lowest overhead, as it will
    only require 1 byte if the packet length is less than
    508 bytes (127 << 2, which is very common).
    """
    async def connect(self, ip, port):
        result = await super().connect(ip, port)
        await self.conn.write(b'\xef')
        return result

    async def recv(self):
        length = struct.unpack('<B', await self.read(1))[0]
        if length >= 127:
            length = struct.unpack('<i', await self.read(3) + b'\0')[0]

        return await self.read(length << 2)

    async def send(self, message):
        length = len(message) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        await self.write(length + message)
