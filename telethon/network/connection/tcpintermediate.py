import struct

from .tcpfull import ConnectionTcpFull


class ConnectionTcpIntermediate(ConnectionTcpFull):
    """
    Intermediate mode between `ConnectionTcpFull` and `ConnectionTcpAbridged`.
    Always sends 4 extra bytes for the packet length.
    """
    async def connect(self, ip, port):
        result = await super().connect(ip, port)
        await self.conn.write(b'\xee\xee\xee\xee')
        return result

    async def recv(self):
        return await self.read(struct.unpack('<i', await self.read(4))[0])

    async def send(self, message):
        await self.write(struct.pack('<i', len(message)) + message)
