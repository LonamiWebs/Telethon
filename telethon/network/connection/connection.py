import abc
import asyncio
import logging
import socket
import ssl as ssl_mod

__log__ = logging.getLogger(__name__)


class Connection(abc.ABC):
    """
    The `Connection` class is a wrapper around ``asyncio.open_connection``.

    Subclasses are meant to communicate with this class through a queue.

    This class provides a reliable interface that will stay connected
    under any conditions for as long as the user doesn't disconnect or
    the input parameters to auto-reconnect dictate otherwise.
    """
    def __init__(self, ip, port, *, loop, proxy=None):
        self._ip = ip
        self._port = port
        self._loop = loop
        self._proxy = proxy
        self._reader = None
        self._writer = None
        self._disconnected = asyncio.Event(loop=loop)
        self._disconnected.set()
        self._disconnected_future = None
        self._send_task = None
        self._recv_task = None
        self._send_queue = asyncio.Queue(1)
        self._recv_queue = asyncio.Queue(1)

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

            self._reader, self._writer = await asyncio.open_connection(
                self._ip, self._port, loop=self._loop, sock=s
            )

        self._disconnected.clear()
        self._disconnected_future = None
        self._send_task = self._loop.create_task(self._send_loop())
        self._recv_task = self._loop.create_task(self._recv_loop())

    def disconnect(self):
        """
        Disconnects from the server.
        """
        self._disconnected.set()
        if self._send_task:
            self._send_task.cancel()

        if self._recv_task:
            self._recv_task.cancel()

        if self._writer:
            self._writer.close()

    @property
    def disconnected(self):
        if not self._disconnected_future:
            self._disconnected_future = \
                self._loop.create_task(self._disconnected.wait())
        return self._disconnected_future

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
        return self._send_queue.put(data)

    async def recv(self):
        """
        Receives a packet of data through this connection mode.

        This method returns a coroutine.
        """
        ok, result = await self._recv_queue.get()
        if ok:
            return result
        else:
            raise result from None

    # TODO Get/put to the queue with cancellation
    async def _send_loop(self):
        """
        This loop is constantly popping items off the queue to send them.
        """
        try:
            while not self._disconnected.is_set():
                self._send(await self._send_queue.get())
                await self._writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception('Unhandled exception in the sending loop')
            self.disconnect()

    async def _recv_loop(self):
        """
        This loop is constantly putting items on the queue as they're read.
        """
        try:
            while not self._disconnected.is_set():
                data = await self._recv()
                await self._recv_queue.put((True, data))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._recv_queue.put((False, e))
            self.disconnect()

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
