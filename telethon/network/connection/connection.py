import abc
import asyncio
import socket
import ssl as ssl_mod

from ...errors import InvalidChecksumError


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
    def __init__(self, ip, port, *, loop, loggers, proxy=None):
        self._ip = ip
        self._port = port
        self._loop = loop
        self._log = loggers[__name__]
        self._proxy = proxy
        self._reader = None
        self._writer = None
        self._connected = False
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
                s.settimeout(timeout)
                s = ssl_mod.wrap_socket(
                    s,
                    do_handshake_on_connect=True,
                    ssl_version=ssl_mod.PROTOCOL_SSLv23,
                    ciphers='ADH-AES256-SHA'
                )
                s.setblocking(False)

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
        self._connected = False

        if self._send_task:
            self._send_task.cancel()

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
            if isinstance(e, ConnectionError):
                self._log.info('The server closed the connection while sending')
            else:
                self._log.exception('Unexpected exception in the send loop')

            self.disconnect()

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
                if isinstance(e, (ConnectionError, asyncio.IncompleteReadError)):
                    msg = 'The server closed the connection'
                    self._log.info(msg)
                elif isinstance(e, InvalidChecksumError):
                    msg = 'The server response had an invalid checksum'
                    self._log.info(msg)
                else:
                    msg = 'Unexpected exception in the receive loop'
                    self._log.exception(msg)

                self.disconnect()

                # Add a sentinel value to unstuck recv
                if self._recv_queue.empty():
                    self._recv_queue.put_nowait(None)

                break

            try:
                await self._recv_queue.put(data)
            except asyncio.CancelledError:
                break

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
