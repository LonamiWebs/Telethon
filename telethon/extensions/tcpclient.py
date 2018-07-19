"""
This module holds a rough implementation of the C# TCP client.

This class is **not** safe across several tasks since partial reads
may be ``await``'ed before being able to return the exact byte count.

This class is also not concerned about disconnections or retries of
any sort, nor any other kind of errors such as connecting twice.
"""
import asyncio
import errno
import logging
import socket
import ssl
from io import BytesIO

CONN_RESET_ERRNOS = {
    errno.EBADF, errno.ENOTSOCK, errno.ENETUNREACH,
    errno.EINVAL, errno.ENOTCONN, errno.EHOSTUNREACH,
    errno.ECONNREFUSED, errno.ECONNRESET, errno.ECONNABORTED,
    errno.ENETDOWN, errno.ENETRESET, errno.ECONNABORTED,
    errno.EHOSTDOWN, errno.EPIPE, errno.ESHUTDOWN
}
# catched: EHOSTUNREACH, ECONNREFUSED, ECONNRESET, ENETUNREACH
# ConnectionError: EPIPE, ESHUTDOWN, ECONNABORTED, ECONNREFUSED, ECONNRESET

try:
    import socks
except ImportError:
    socks = None

SSL_PORT = 443
__log__ = logging.getLogger(__name__)


class TcpClient:
    """A simple TCP client to ease the work with sockets and proxies."""

    class SocketClosed(ConnectionError):
        pass

    def __init__(self, *, loop, timeout, ssl=None, proxy=None):
        """
        Initializes the TCP client.

        :param proxy: the proxy to be used, if any.
        :param timeout: the timeout for connect, read and write operations.
        :param ssl: ssl.wrap_socket keyword arguments to use when connecting
                    if port == SSL_PORT, or do nothing if not present.
        """
        self._loop = loop
        self.proxy = proxy
        self.ssl = ssl
        self._socket = None
        self._closed = asyncio.Event(loop=self._loop)
        self._closed.set()

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
        Tries connecting to IP:port unless an OSError is raised.

        :param ip: the IP to connect to.
        :param port: the port to connect to.
        """
        if ':' in ip:  # IPv6
            ip = ip.replace('[', '').replace(']', '')
            mode, address = socket.AF_INET6, (ip, port, 0, 0)
        else:
            mode, address = socket.AF_INET, (ip, port)

        try:
            if self._socket is None:
                self._socket = self._create_socket(mode, self.proxy)
                wrap_ssl = self.ssl and port == SSL_PORT
            else:
                wrap_ssl = False

            await asyncio.wait_for(
                self._loop.sock_connect(self._socket, address),
                timeout=self.timeout,
                loop=self._loop
            )
            if wrap_ssl:
                # Temporarily set the socket to blocking
                # (timeout) until connection is established.
                self._socket.settimeout(self.timeout)
                self._socket = ssl.wrap_socket(
                    self._socket, do_handshake_on_connect=True, **self.ssl)
                self._socket.setblocking(False)

            self._closed.clear()
        except OSError as e:
            if e.errno in CONN_RESET_ERRNOS:
                raise ConnectionResetError() from e
            else:
                raise

    @property
    def is_connected(self):
        """Determines whether the client is connected or not."""
        return not self._closed.is_set()

    def close(self):
        """Closes the connection."""
        fd = None
        try:
            if self._socket is not None:
                fd = self._socket.fileno()
                if self.is_connected:
                    self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
        except OSError:
            pass  # Ignore ENOTCONN, EBADF, and any other error when closing
        finally:
            self._socket = None
            self._closed.set()
            if fd and fd != -1:
                self._loop.remove_reader(fd)

    async def _wait_timeout_or_close(self, coro):
        """
        Waits for the given coroutine to complete unless
        the socket is closed or `self.timeout` expires.
        """
        done, running = await asyncio.wait(
            [coro, self._closed.wait()],
            timeout=self.timeout,
            return_when=asyncio.FIRST_COMPLETED,
            loop=self._loop
        )
        for r in running:
            r.cancel()
        if not self.is_connected:
            raise self.SocketClosed()
        if not done:
            raise asyncio.TimeoutError()
        return done.pop().result()

    async def write(self, data):
        """
        Writes (sends) the specified bytes to the connected peer.
        :param data: the data to send.
        """
        if not self.is_connected:
            raise ConnectionResetError('Not connected')

        try:
            await self._wait_timeout_or_close(self.sock_sendall(data))
        except OSError as e:
            if e.errno in CONN_RESET_ERRNOS:
                raise ConnectionResetError() from e
            else:
                raise

    async def read(self, size):
        """
        Reads (receives) a whole block of size bytes from the connected peer.

        :param size: the size of the block to be read.
        :return: the read data with len(data) == size.
        """
        if not self.is_connected:
            raise ConnectionResetError('Not connected')

        with BytesIO() as buffer:
            bytes_left = size
            while bytes_left != 0:
                try:
                    partial = await self._wait_timeout_or_close(
                        self.sock_recv(bytes_left)
                    )
                except asyncio.TimeoutError:
                    if bytes_left < size:
                        __log__.warning(
                            'Timeout when partial %d/%d had been received',
                            size - bytes_left, size
                        )
                    raise
                except OSError as e:
                    if e.errno in CONN_RESET_ERRNOS:
                        raise ConnectionResetError() from e
                    else:
                        raise

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
        if fut.cancelled() or self._socket is None:
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
        if fut.cancelled() or self._socket is None:
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
