import abc
import asyncio
import logging
import socket
import ssl as ssl_mod

from ...errors import InvalidChecksumError

__log__ = logging.getLogger(__name__)


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
    def __init__(self, ip, port, *, loop, proxy=None):
        self._ip = ip
        self._port = port
        self._loop = loop
        self._proxy = proxy
        self._reader = None
        self._writer = None
        self._connected = False
        self._send_task = None
        self._recv_task = None
        self._send_queue = asyncio.Queue(1)
        self._recv_queue = asyncio.Queue(1)
        self._waiting_recv = False

    async def connect(self, timeout=None, ssl=None):
        """
        Establishes a connection with the server.
        """
        if not self._proxy:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self._ip, self._port, loop=self._loop, ssl=ssl),
                loop=self._loop, timeout=timeout
            )
        else:
            import socks
            if ':' in self._ip:
                mode, address = socket.AF_INET6, (self._ip, self._port, 0, 0)
            else:
                mode, address = socket.AF_INET, (self._ip, self._port)

            s = socks.socksocket(mode, socket.SOCK_STREAM)
            if isinstance(self._proxy, dict):
                s.set_proxy(**self._proxy)
            else:
                s.set_proxy(*self._proxy)

            s.setblocking(False)
            await asyncio.wait_for(
                self._loop.sock_connect(s, address),
                timeout=timeout,
                loop=self._loop
            )
            if ssl:
                self._socket.settimeout(timeout)
                self._socket = ssl_mod.wrap_socket(
                    s,
                    do_handshake_on_connect=True,
                    ssl_version=ssl_mod.PROTOCOL_SSLv23,
                    ciphers='ADH-AES256-SHA'
                )
                self._socket.setblocking(False)

            self._reader, self._writer = \
                await asyncio.open_connection(sock=s, loop=self._loop)

        self._connected = True
        self._send_task = self._loop.create_task(self._send_loop())
        self._recv_task = self._loop.create_task(self._recv_loop())

    def disconnect(self):
        """
        Disconnects from the server, and clears
        pending outgoing and incoming messages.
        """
        self._disconnect(error=None)

    def _disconnect(self, error):
        self._connected = False

        while not self._send_queue.empty():
            self._send_queue.get_nowait()

        if self._send_task:
            self._send_task.cancel()

        while not self._recv_queue.empty():
            self._recv_queue.get_nowait()

        if self._recv_task:
            self._recv_task.cancel()

        if self._writer:
            self._writer.close()

    def clone(self):
        """
        Creates a clone of the connection.
        """
        return self.__class__(self._ip, self._port, loop=self._loop)

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
        if not self._connected:
            raise ConnectionError('Not connected')

        self._waiting_recv = True
        result = await self._recv_queue.get()
        self._waiting_recv = False

        if result:
            return result
        else:
            raise ConnectionError('The server closed the connection')

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
        except Exception:
            msg = 'Unexpected exception in the send loop'
            __log__.exception(msg)
            self._disconnect(ConnectionError(msg))

    async def _recv_loop(self):
        """
        This loop is constantly putting items on the queue as they're read.
        """
        try:
            while self._connected:
                data = await self._recv()
                await self._recv_queue.put(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if isinstance(e, (ConnectionError, asyncio.IncompleteReadError)):
                msg = 'The server closed the connection'
                __log__.info(msg)
            elif isinstance(e, InvalidChecksumError):
                msg = 'The server response had an invalid checksum'
                __log__.info(msg)
            else:
                msg = 'Unexpected exception in the receive loop'
                __log__.exception(msg)

            if self._waiting_recv and not self._recv_queue.empty():
                await self._recv_queue.put_nowait(None)

            self._disconnect(ConnectionError(msg))

    @abc.abstractmethod
    def _send(self, data):
        """
        This method should be implemented differently under each
        connection mode and serialize the data into the packet
        the way it should be sent through `self._writer`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def _recv(self):
        """
        This method should be implemented differently under each
        connection mode and deserialize the data from the packet
        the way it should be read from `self._reader`.
        """
        raise NotImplementedError

    def __str__(self):
        return '{}:{}/{}'.format(
            self._ip, self._port,
            self.__class__.__name__.replace('Connection', '')
        )
