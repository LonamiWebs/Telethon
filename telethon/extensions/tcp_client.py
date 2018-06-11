"""
This module holds a rough implementation of the C# TCP client.

This class is **not** safe across several tasks since partial reads
may be ``await``'ed before being able to return the exact byte count.

This class is also not concerned about disconnections or retries of
any sort, nor any other kind of errors such as connecting twice.
"""
import asyncio
import logging
import socket
from io import BytesIO

try:
    import socks
except ImportError:
    socks = None


__log__ = logging.getLogger(__name__)


class TcpClient:
    """A simple TCP client to ease the work with sockets and proxies."""
    def __init__(self, proxy=None, timeout=5):
        """
        Initializes the TCP client.

        :param proxy: the proxy to be used, if any.
        :param timeout: the timeout for connect, read and write operations.
        """
        self.proxy = proxy
        self._socket = None
        self._loop = asyncio.get_event_loop()

        if isinstance(timeout, (int, float)):
            self.timeout = float(timeout)
        elif hasattr(timeout, 'seconds'):
            self.timeout = float(timeout.seconds)
        else:
            raise TypeError('Invalid timeout type: {}'.format(type(timeout)))

    @staticmethod
    def _create_socket(mode, proxy):
        if proxy is None:
            s = socket.socket(mode, socket.SOCK_STREAM)
        else:
            import socks
            s = socks.socksocket(mode, socket.SOCK_STREAM)
            if isinstance(proxy, dict):
                s.set_proxy(**proxy)
            else:  # tuple, list, etc.
                s.set_proxy(*proxy)
        s.setblocking(False)
        return s

    async def connect(self, ip, port):
        """
        Tries connecting to IP:port.

        :param ip: the IP to connect to.
        :param port: the port to connect to.
        """
        if ':' in ip:  # IPv6
            ip = ip.replace('[', '').replace(']', '')
            mode, address = socket.AF_INET6, (ip, port, 0, 0)
        else:
            mode, address = socket.AF_INET, (ip, port)

        if self._socket is None:
            self._socket = self._create_socket(mode, self.proxy)

        await asyncio.wait_for(self._loop.sock_connect(self._socket, address),
                               self.timeout, loop=self._loop)

    @property
    def is_connected(self):
        """Determines whether the client is connected or not."""
        # TODO fileno() is >= 0 even before calling sock_connect!
        return self._socket is not None and self._socket.fileno() >= 0

    def close(self):
        """Closes the connection."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            finally:
                self._socket = None

    async def write(self, data):
        """
        Writes (sends) the specified bytes to the connected peer.

        :param data: the data to send.
        """
        if not self.is_connected:
            raise ConnectionError()

        await asyncio.wait_for(
            self.sock_sendall(data),
            timeout=self.timeout,
            loop=self._loop
        )

    async def read(self, size):
        """
        Reads (receives) a whole block of size bytes from the connected peer.

        :param size: the size of the block to be read.
        :return: the read data with len(data) == size.
        """
        if not self.is_connected:
            raise ConnectionError()

        with BytesIO() as buffer:
            bytes_left = size
            while bytes_left != 0:
                partial = await asyncio.wait_for(
                    self.sock_recv(bytes_left),
                    timeout=self.timeout,
                    loop=self._loop
                )
                if not partial:
                    raise ConnectionResetError()

                buffer.write(partial)
                bytes_left -= len(partial)

            return buffer.getvalue()

    # Due to recent https://github.com/python/cpython/pull/4386
    # Credit to @andr-04 for his original implementation
    def sock_recv(self, n):
        fut = self._loop.create_future()
        self._sock_recv(fut, None, n)
        return fut

    def _sock_recv(self, fut, registered_fd, n):
        if registered_fd is not None:
            self._loop.remove_reader(registered_fd)
        if fut.cancelled():
            return

        try:
            data = self._socket.recv(n)
        except (BlockingIOError, InterruptedError):
            fd = self._socket.fileno()
            self._loop.add_reader(fd, self._sock_recv, fut, fd, n)
        except Exception as exc:
            fut.set_exception(exc)
        else:
            fut.set_result(data)

    def sock_sendall(self, data):
        fut = self._loop.create_future()
        if data:
            self._sock_sendall(fut, None, data)
        else:
            fut.set_result(None)
        return fut

    def _sock_sendall(self, fut, registered_fd, data):
        if registered_fd:
            self._loop.remove_writer(registered_fd)
        if fut.cancelled():
            return

        try:
            n = self._socket.send(data)
        except (BlockingIOError, InterruptedError):
            n = 0
        except Exception as exc:
            fut.set_exception(exc)
            return

        if n == len(data):
            fut.set_result(None)
        else:
            if n:
                data = data[n:]
            fd = self._socket.fileno()
            self._loop.add_writer(fd, self._sock_sendall, fut, fd, data)
