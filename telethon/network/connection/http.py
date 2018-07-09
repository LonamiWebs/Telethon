import errno
import ssl

from .common import Connection
from ...extensions import TcpClient


class ConnectionHttp(Connection):
    def __init__(self, *, loop, timeout, proxy=None):
        super().__init__(loop=loop, timeout=timeout, proxy=proxy)
        self.conn = TcpClient(
            timeout=self._timeout, loop=self._loop, proxy=self._proxy,
            ssl=dict(ssl_version=ssl.PROTOCOL_SSLv23, ciphers='ADH-AES256-SHA')
        )
        self.read = self.conn.read
        self.write = self.conn.write
        self._host = None

    async def connect(self, ip, port):
        self._host = '{}:{}'.format(ip, port)
        try:
            await self.conn.connect(ip, port)
        except OSError as e:
            if e.errno == errno.EISCONN:
                return  # Already connected, no need to re-set everything up
            else:
                raise

    def get_timeout(self):
        return self.conn.timeout

    def is_connected(self):
        return self.conn.is_connected

    async def close(self):
        self.conn.close()

    async def recv(self):
        while True:
            line = await self._read_line()
            if line.lower().startswith(b'content-length: '):
                await self.read(2)
                length = int(line[16:-2])
                return await self.read(length)

    async def _read_line(self):
        newline = ord('\n')
        line = await self.read(1)
        while line[-1] != newline:
            line += await self.read(1)
        return line

    async def send(self, message):
        await self.write(
            'POST /api HTTP/1.1\r\n'
            'Host: {}\r\n'
            'Content-Type: application/x-www-form-urlencoded\r\n'
            'Connection: keep-alive\r\n'
            'Keep-Alive: timeout=100000, max=10000000\r\n'
            'Content-Length: {}\r\n\r\n'.format(self._host, len(message))
            .encode('ascii') + message
        )
