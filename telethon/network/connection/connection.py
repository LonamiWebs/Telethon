import abc
import asyncio
import sys

try:
    import ssl as ssl_mod
except ImportError:
    ssl_mod = None

from ...errors import InvalidChecksumError
from ... import helpers

import aiosocks

# For some reason, `aiosocks` internal errors are not inherited from
# builtin IOError (just from Exception). Instead of adding those
# in exceptions clauses everywhere through the code, we
# rather monkey-patch them in place.

aiosocks.errors.SocksError = ConnectionError
aiosocks.errors.NoAcceptableAuthMethods = ConnectionError
aiosocks.errors.LoginAuthenticationFailed = ConnectionError
aiosocks.errors.InvalidServerVersion = ConnectionError
aiosocks.errors.InvalidServerReply = ConnectionError
aiosocks.errors.SocksConnectionError = ConnectionError


class Connection(abc.ABC):
    """
    The `Connection` class is a wrapper around ``asyncio.open_connection``.

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

    def __init__(self, ip, port, dc_id, *, loggers, proxy=None, local_addr=None):
        self._ip = ip
        self._port = port
        self._dc_id = dc_id  # only for MTProxy, it's an abstraction leak
        self._log = loggers[__name__]
        self._proxy = proxy
        self._local_addr = local_addr
        self._reader = None
        self._writer = None
        self._connected = False
        self._send_task = None
        self._recv_task = None
        self._codec = None
        self._obfuscation = None  # TcpObfuscated and MTProxy
        self._send_queue = asyncio.Queue(1)
        self._recv_queue = asyncio.Queue(1)

    async def _connect(self, timeout=None, ssl=None):

        if self._local_addr is not None:

            # NOTE: If port is not specified, we use 0 port
            # to notify the OS that port should be chosen randomly
            # from the available ones.

            if isinstance(self._local_addr, tuple) and len(self._local_addr) == 2:
                local_addr = self._local_addr
            elif isinstance(self._local_addr, str):
                local_addr = (self._local_addr, 0)
            else:
                raise ValueError("Unknown local address format: {}".format(self._local_addr))
        else:
            local_addr = None

        if not self._proxy:
            connect_coroutine = asyncio.open_connection(
                host=self._ip,
                port=self._port,
                ssl=ssl,
                local_addr=local_addr)
        else:

            if isinstance(self._proxy, (tuple, list)):
                proxy, auth, remote_resolve = self._parse_proxy(*self._proxy)
            elif isinstance(self._proxy, dict):
                proxy, auth, remote_resolve = self._parse_proxy(**self._proxy)
            else:
                raise ValueError("Unknown proxy format: {}".format(self._proxy.__class__.__name__))

            connect_coroutine = aiosocks.open_connection(
                proxy=proxy,
                proxy_auth=auth,
                dst=(self._ip, self._port),
                remote_resolve=remote_resolve,
                ssl=ssl,
                local_addr=local_addr)

        self._reader, self._writer = await asyncio.wait_for(connect_coroutine, timeout=timeout)
        self._codec = self.packet_codec(self)
        self._init_conn()
        await self._writer.drain()

    @staticmethod
    def _parse_proxy(proxy_type, addr, port, rdns=True, username=None, password=None):

        proxy, auth = None, None

        if isinstance(proxy_type, str):
            proxy_type = proxy_type.lower()

        # We do the check for numerical values here
        # to be backwards compatible with PySocks proxy format,
        # (since socks.SOCKS5 = 2 and socks.SOCKS4 = 1)

        if proxy_type == 'socks5' or proxy_type == 2:
            proxy = aiosocks.Socks5Addr(addr, port)
            if username and password:
                auth = aiosocks.Socks5Auth(username, password)

        elif proxy_type == 'socks4' or proxy_type == 1:
            proxy = aiosocks.Socks4Addr(addr, port)
            if username:
                auth = aiosocks.Socks4Auth(username)
        else:
            raise ValueError('Unsupported proxy protocol {}'.format(proxy_type))

        return proxy, auth, rdns

    async def connect(self, timeout=None, ssl=None):
        """
        Establishes a connection with the server.
        """
        await self._connect(timeout=timeout, ssl=ssl)
        self._connected = True

        loop = asyncio.get_event_loop()
        self._send_task = loop.create_task(self._send_loop())
        self._recv_task = loop.create_task(self._recv_loop())

    async def disconnect(self):
        """
        Disconnects from the server, and clears
        pending outgoing and incoming messages.
        """
        self._connected = False

        await helpers._cancel(
            self._log,
            send_task=self._send_task,
            recv_task=self._recv_task
        )

        if self._writer:
            self._writer.close()
            if sys.version_info >= (3, 7):
                try:
                    await self._writer.wait_closed()
                except Exception as e:
                    # Disconnecting should never raise. Seen:
                    # * OSError: No route to host and
                    # * OSError: [Errno 32] Broken pipe
                    # * ConnectionResetError
                    self._log.info('%s during disconnect: %s', type(e), e)

    def send(self, data):
        """
        Sends a packet of data through this connection mode.

        This method returns a coroutine.
        """
        if not self._connected:
            raise ConnectionError('Not connected')

        return self._send_queue.put(data)

    async def recv(self):
        """
        Receives a packet of data through this connection mode.

        This method returns a coroutine.
        """
        while self._connected:
            result = await self._recv_queue.get()
            if result:  # None = sentinel value = keep trying
                return result

        raise ConnectionError('Not connected')

    async def _send_loop(self):
        """
        This loop is constantly popping items off the queue to send them.
        """
        try:
            while self._connected:
                self._send(await self._send_queue.get())
                await self._writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if isinstance(e, IOError):
                self._log.info('The server closed the connection while sending')
            else:
                self._log.exception('Unexpected exception in the send loop')

            await self.disconnect()

    async def _recv_loop(self):
        """
        This loop is constantly putting items on the queue as they're read.
        """
        while self._connected:
            try:
                data = await self._recv()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if isinstance(e, (IOError, asyncio.IncompleteReadError)):
                    msg = 'The server closed the connection'
                    self._log.info(msg)
                elif isinstance(e, InvalidChecksumError):
                    msg = 'The server response had an invalid checksum'
                    self._log.info(msg)
                else:
                    msg = 'Unexpected exception in the receive loop'
                    self._log.exception(msg)

                await self.disconnect()

                # Add a sentinel value to unstuck recv
                if self._recv_queue.empty():
                    self._recv_queue.put_nowait(None)

                break

            try:
                await self._recv_queue.put(data)
            except asyncio.CancelledError:
                break

    def _init_conn(self):
        """
        This method will be called after `connect` is called.
        After this method finishes, the writer will be drained.

        Subclasses should make use of this if they need to send
        data to Telegram to indicate which connection mode will
        be used.
        """
        if self._codec.tag:
            self._writer.write(self._codec.tag)

    def _send(self, data):
        self._writer.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._reader)

    def __str__(self):
        return '{}:{}/{}'.format(
            self._ip, self._port,
            self.__class__.__name__.replace('Connection', '')
        )


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
    "magic bytes" should be sent to server right after connection is made to
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
