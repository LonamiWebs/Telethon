import asyncio

from .connection import Connection


SSL_PORT = 443


class ConnectionHttp(Connection):
    async def connect(self, timeout=None, ssl=None):
        await super().connect(timeout=timeout, ssl=self._port == SSL_PORT)

    def _send(self, message):
        self._writer.write(
            'POST /api HTTP/1.1\r\n'
            'Host: {}:{}\r\n'
            'Content-Type: application/x-www-form-urlencoded\r\n'
            'Connection: keep-alive\r\n'
            'Keep-Alive: timeout=100000, max=10000000\r\n'
            'Content-Length: {}\r\n\r\n'
            .format(self._ip, self._port, len(message))
            .encode('ascii') + message
        )

    async def _recv(self):
        while True:
            line = await self._reader.readline()
            if not line or line[-1] != b'\n':
                raise asyncio.IncompleteReadError(line, None)

            if line.lower().startswith(b'content-length: '):
                await self._reader.readexactly(2)
                length = int(line[16:-2])
                return await self._reader.readexactly(length)
