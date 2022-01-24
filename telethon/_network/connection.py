import asyncio
import socket

from .transports.transport import Transport


CHUNK_SIZE = 32 * 1024


# TODO ideally the mtproto impl would also be sans-io, but that's less pressing
class Connection:
    def __init__(self, ip, port, *, transport: Transport, loggers, local_addr=None):
        self._ip = ip
        self._port = port
        self._log = loggers[__name__]
        self._local_addr = local_addr

        self._sock = None
        self._in_buffer = bytearray()
        self._transport = transport

    async def connect(self, timeout=None, ssl=None):
        """
        Establishes a connection with the server.
        """
        loop = asyncio.get_running_loop()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        if self._local_addr:
            sock.bind(self._local_addr)

        # TODO https://github.com/LonamiWebs/Telethon/issues/1337 may be an issue again
        # perhaps we just need to ignore async connect on windows and block?
        await asyncio.wait_for(loop.sock_connect(sock, (self._ip, self._port)), timeout)
        self._sock = sock

    async def disconnect(self):
        self._sock.close()
        self._sock = None

    async def send(self, data):
        if not self._sock:
            raise ConnectionError('not connected')

        loop = asyncio.get_running_loop()
        await loop.sock_sendall(self._sock, self._transport.pack(data))

    async def recv(self):
        if not self._sock:
            raise ConnectionError('not connected')

        loop = asyncio.get_running_loop()
        while True:
            try:
                length, body = self._transport.unpack(self._in_buffer)
                del self._in_buffer[:length]
                return body
            except EOFError:
                self._in_buffer += await loop.sock_recv(self._sock, CHUNK_SIZE)

    def __str__(self):
        return f'{self._ip}:{self._port}/{self._transport.__class__.__name__}'
