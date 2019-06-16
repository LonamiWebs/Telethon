import abc
import asyncio
import socket
import ssl as ssl_mod
import sys

from ...errors import InvalidChecksumError
from ... import helpers
from .baseconnection import BaseConnection


class AsyncioConnection(BaseConnection):
    """
    The `AsyncioConnection` class is a wrapper around ``asyncio.open_connection``.

    Subclasses will implement different transport modes as atomic operations,
    which this class eases doing since the exposed interface simply puts and
    gets complete data payloads to and from queues.

    The only error that will raise from send and receive methods is
    ``ConnectionError``, which will raise when attempting to send if
    the client is disconnected (includes remote disconnections).
    """
    # this static attribute should be redefined by `Connection` subclasses and
    # should be one of `PacketCodec` implementations
    packet_codec = None

    def __init__(self, ip, port, dc_id, *, loop, codec, loggers, proxy=None):
        super().__init__(ip, port, loop=loop, codec=codec)
        self._dc_id = dc_id  # only for MTProxy, it's an abstraction leak
        self._log = loggers[__name__]
        self._proxy = proxy
        self._reader = None
        self._writer = None
        self._connected = False
        self._obfuscation = None  # TcpObfuscated and MTProxy

    async def _connect(self, timeout=None, ssl=None):
        if not self._proxy:
            connect_coroutine = asyncio.open_connection(
                self._ip, self._port, loop=self._loop, ssl=ssl)
        else:
            import aiosocks

            auth = None
            proto = self._proxy.get('protocol', 'socks5').lower()
            if proto == 'socks5':
                proxy = aiosocks.Socks5Addr(self._proxy['host'], self._proxy['port'])
                if 'username' in self._proxy:
                    auth = aiosocks.Socks5Auth(self._proxy['username'], self._proxy['password'])

            elif proto == 'socks4':
                proxy = aiosocks.Socks4Addr(self._proxy['host'], self._proxy['port'])
                if 'username' in self._proxy:
                    auth = aiosocks.Socks4Auth(self._proxy['username'])

            else:
                raise ValueError('Unsupported proxy protocol {}'.format(self._proxy['protocol']))

            connect_coroutine = aiosocks.open_connection(
                proxy=proxy,
                proxy_auth=auth,
                dst=(self._ip, self._port),
                remote_resolve=self._proxy.get('remote_resolve', True),
                loop=self._loop,
                ssl=ssl
            )

        self._reader, self._writer = await asyncio.wait_for(
            connect_coroutine,
            loop=self._loop, timeout=timeout
        )

        self._codec.__init__()  # reset the codec
        if self._codec.tag():
            await self._send(self._codec.tag())

    @property
    def connected(self):
        return self._connected

    async def connect(self, timeout=None, ssl=None):
        """
        Establishes a connection with the server.
        """
        await self._connect(timeout=timeout, ssl=ssl)
        self._connected = True

    async def disconnect(self):
        """
        Disconnects from the server, and clears
        pending outgoing and incoming messages.
        """
        self._connected = False

        if self._writer:
            self._writer.close()
            if sys.version_info >= (3, 7):
                try:
                    await self._writer.wait_closed()
                except Exception as e:
                    # Seen OSError: No route to host
                    # Disconnecting should never raise
                    self._log.warning('Unhandled %s on disconnect: %s', type(e), e)

    async def _send(self, data):
        self._writer.write(data)
        await self._writer.drain()

    async def _recv(self, length):
        return await self._reader.readexactly(length)


class Connection(abc.ABC):
    pass


class ObfuscatedConnection(Connection):
    """
    Base class for "obfuscated" connections ("obfuscated2", "mtproto proxy")
    """
    """
    This attribute should be redefined by subclasses
    """
    obfuscated_io = None

    def _init_conn(self):
        self._obfuscation = self.obfuscated_io(self)
        self._writer.write(self._obfuscation.header)

    def _send(self, data):
        self._obfuscation.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._obfuscation)


class PacketCodec(abc.ABC):
    """
    Base class for packet codecs
    """

    """
    This attribute should be re-defined by subclass to define if some
    "magic bytes" should be sent to server right after conection is made to
    signal which protocol will be used
    """
    tag = None

    def __init__(self, connection):
        """
        Codec is created when connection is just made.
        """
        self._conn = connection

    @abc.abstractmethod
    def encode_packet(self, data):
        """
        Encodes single packet and returns encoded bytes.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def read_packet(self, reader):
        """
        Reads single packet from `reader` object that should have
        `readexactly(n)` method.
        """
        raise NotImplementedError
