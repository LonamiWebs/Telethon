import abc
import asyncio

from ..codec import BaseCodec


class BaseConnection(abc.ABC):
    """
    The base connection class.

    It offers atomic send and receive methods.

    Subclasses are only responsible of sending and receiving data,
    since this base class already makes use of the given codec for
    correctly adapting the data.
    """
    def __init__(self, ip: str, port: int, *, loop: asyncio.AbstractEventLoop, codec: BaseCodec):
        self._ip = ip
        self._port = port
        self._loop = loop
        self._codec = codec
        self._send_lock = asyncio.Lock(loop=loop)
        self._recv_lock = asyncio.Lock(loop=loop)

    @property
    @abc.abstractmethod
    def connected(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def connect(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def disconnect(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def _send(self, data):
        raise NotImplementedError

    @abc.abstractmethod
    async def _recv(self, length):
        raise NotImplementedError

    async def send(self, data):
        if not self.connected:
            raise ConnectionError('Not connected')

        # TODO Handle asyncio.CancelledError, IOError, Exception
        data = self._codec.encode_packet(data)
        async with self._send_lock:
            return await self._send(data)

    async def recv(self):
        if not self.connected:
            raise ConnectionError('Not connected')

        # TODO Handle asyncio.CancelledError, asyncio.IncompleteReadError,
        #      IOError, InvalidChecksumError, Exception properly
        await self._recv_lock.acquire()
        try:
            header = await self._recv(self._codec.header_length())

            length = self._codec.decode_header(header)
            while length < 0:
                header += await self._recv(-length)
                length = self._codec.decode_header(header)

            body = await self._recv(length)
            return self._codec.decode_body(header, body)
        except Exception:
            raise ConnectionError
        finally:
            self._recv_lock.release()

    def __str__(self):
        return '{}:{}/{}'.format(
            self._ip, self._port,
            self.__class__.__name__.replace('Connection', '')
        )
