import struct

from .connection import Connection


class ConnectionTcpAbridged(Connection):
    """
    This is the mode with the lowest overhead, as it will
    only require 1 byte if the packet length is less than
    508 bytes (127 << 2, which is very common).
    """
    async def connect(self, timeout=None, ssl=None):
        await super().connect(timeout=timeout, ssl=ssl)
        self._writer.write(b'\xef')
        await self._writer.drain()

    def _write(self, data):
        """
        Define wrapper write methods for `TcpObfuscated` to override.
        """
        self._writer.write(data)

    async def _read(self, n):
        """
        Define wrapper read methods for `TcpObfuscated` to override.
        """
        return await self._reader.readexactly(n)

    def _send(self, data):
        length = len(data) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        self._write(length + data)

    async def _recv(self):
        length = struct.unpack('<B', await self._read(1))[0]
        if length >= 127:
            length = struct.unpack(
                '<i', await self._read(3) + b'\0')[0]

        return await self._read(length << 2)
