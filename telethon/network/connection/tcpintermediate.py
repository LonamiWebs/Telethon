import struct

from .connection import Connection


class ConnectionTcpIntermediate(Connection):
    """
    Intermediate mode between `ConnectionTcpFull` and `ConnectionTcpAbridged`.
    Always sends 4 extra bytes for the packet length.
    """
    async def connect(self, timeout=None, ssl=None):
        await super().connect(timeout=timeout, ssl=ssl)
        self._writer.write(b'\xee\xee\xee\xee')
        await self._writer.drain()

    def _send(self, data):
        self._writer.write(struct.pack('<i', len(data)) + data)

    async def _recv(self):
        return await self._reader.readexactly(
            struct.unpack('<i', await self._reader.readexactly(4))[0])
