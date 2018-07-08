from .tcpfull import ConnectionTcpFull


class ConnectionHttp(ConnectionTcpFull):
    def __init__(self, *, loop, timeout, proxy=None):
        super().__init__(loop=loop, timeout=timeout, proxy=proxy)
        self._host = None

    async def connect(self, ip, port):
        if port != 80:
            port = 80  # HTTP without TLS needs port 80

        self._host = '{}:{}'.format(ip, port)
        return await super().connect(ip, port)

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
