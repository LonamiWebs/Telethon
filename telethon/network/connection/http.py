import asyncio

from .connection import Connection


class ConnectionHttp(Connection):
    async def connect(self, timeout=None):
        # TODO Test if the ssl part works or it needs to be as before:
        # dict(ssl_version=ssl.PROTOCOL_SSLv23, ciphers='ADH-AES256-SHA')
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(
                self._ip, self._port, loop=self._loop, ssl=True),
            loop=self._loop, timeout=timeout
        )

        self._disconnected.clear()
        self._disconnected_future = None
        self._send_task = self._loop.create_task(self._send_loop())
        self._recv_task = self._loop.create_task(self._send_loop())

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
