import abc
import asyncio
import logging


__log__ = logging.getLogger(__name__)


class Connection(abc.ABC):
    """
    The `Connection` class is a wrapper around ``asyncio.open_connection``.

    Subclasses are meant to communicate with this class through a queue.

    This class provides a reliable interface that will stay connected
    under any conditions for as long as the user doesn't disconnect or
    the input parameters to auto-reconnect dictate otherwise.
    """
    # TODO Support proxy
    def __init__(self, ip, port, *, loop):
        self._ip = ip
        self._port = port
        self._loop = loop
        self._reader = None
        self._writer = None
        self._disconnected = asyncio.Event(loop=loop)
        self._disconnected.set()
        self._disconnected_future = None
        self._send_task = None
        self._recv_task = None
        self._send_queue = asyncio.Queue(1)
        self._recv_queue = asyncio.Queue(1)

    async def connect(self, timeout=None):
        """
        Establishes a connection with the server.
        """
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._ip, self._port, loop=self._loop),
            loop=self._loop, timeout=timeout
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
