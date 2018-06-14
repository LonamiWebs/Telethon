"""
This module holds a rough implementation of the C# TCP client.
"""
# Python rough implementation of a C# TCP client
import asyncio
import errno
import logging
import socket
from datetime import timedelta
from io import BytesIO, BufferedWriter

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

__log__ = logging.getLogger(__name__)


class TcpClient:
    """A simple TCP client to ease the work with sockets and proxies."""

    class SocketClosed(ConnectionError):
        pass

    def __init__(self, proxy=None, timeout=timedelta(seconds=5), loop=None):
        """
        Initializes the TCP client.

        :param proxy: the proxy to be used, if any.
        :param timeout: the timeout for connect, read and write operations.
        """
        self.proxy = proxy
        self._socket = None
        self._loop = loop if loop else asyncio.get_event_loop()
        self._closed = asyncio.Event(loop=self._loop)
        self._closed.set()

        if isinstance(timeout, timedelta):
            self.timeout = timeout.seconds
        elif isinstance(timeout, (int, float)):
            self.timeout = float(timeout)
        else:
            raise TypeError('Invalid timeout type: {}'.format(type(timeout)))

    def _recreate_socket(self, mode):
        if self.proxy is None:
            self._socket = socket.socket(mode, socket.SOCK_STREAM)
        else:
            import socks
            self._socket = socks.socksocket(mode, socket.SOCK_STREAM)
            if type(self.proxy) is dict:
                self._socket.set_proxy(**self.proxy)
            else:  # tuple, list, etc.
                self._socket.set_proxy(*self.proxy)

        self._socket.setblocking(False)

    async def connect(self, ip, port):
        """
        Tries connecting forever  to IP:port unless an OSError is raised.

        :param ip: the IP to connect to.
        :param port: the port to connect to.
        """
        if ':' in ip:  # IPv6
            ip = ip.replace('[', '').replace(']', '')
            mode, address = socket.AF_INET6, (ip, port, 0, 0)
        else:
            mode, address = socket.AF_INET, (ip, port)

        try:
            if not self._socket:
                self._recreate_socket(mode)

            await asyncio.wait_for(
                self._loop.sock_connect(self._socket, address),
                timeout=self.timeout,
                loop=self._loop
            )

            self._closed.clear()
        except asyncio.TimeoutError as e:
            raise TimeoutError() from e
        except OSError as e:
            if e.errno in CONN_RESET_ERRNOS:
                self._raise_connection_reset(e)
            else:
                raise

    def _get_connected(self):
        """Determines whether the client is connected or not."""
        return not self._closed.is_set()

    connected = property(fget=_get_connected)

    def close(self):
        """Closes the connection."""
        try:
            if self._socket is not None:
                if self.connected:
                    self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
        except OSError:
            pass  # Ignore ENOTCONN, EBADF, and any other error when closing
        finally:
            self._socket = None
            self._closed.set()

    async def _wait_close(self, coro):
        done, running = await asyncio.wait(
            [coro, self._closed.wait()],
            timeout=self.timeout,
            return_when=asyncio.FIRST_COMPLETED,
            loop=self._loop
        )
        for r in running:
            r.cancel()
        if not self.connected:
            raise self.SocketClosed()
        if not done:
            raise TimeoutError()
        return done.pop().result()

    async def write(self, data):
        """
        Writes (sends) the specified bytes to the connected peer.

        :param data: the data to send.
        """
        if not self.connected:
            raise ConnectionResetError('No connection')
        try:
            await self._wait_close(self.sock_sendall(data))
        except self.SocketClosed:
            raise ConnectionResetError('Socket has closed')
        except OSError as e:
            __log__.info('OSError "%s" while writing data', e)
            if e.errno in CONN_RESET_ERRNOS:
                self._raise_connection_reset(e)
            else:
                raise

    async def read(self, size):
        """
        Reads (receives) a whole block of size bytes from the connected peer.

        :param size: the size of the block to be read.
        :return: the read data with len(data) == size.
        """
        with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
            bytes_left = size
            partial = b''
            while bytes_left != 0:
                if not self.connected:
                    raise ConnectionResetError('No connection')
                try:
                    partial = await self._wait_close(self.sock_recv(bytes_left))
                except TimeoutError as e:
                    # These are somewhat common if the server has nothing
                    # to send to us, so use a lower logging priority.
                    if bytes_left < size:
                        __log__.warning(
                            'socket.timeout "%s" when %d/%d had been received',
                            e, size - bytes_left, size
                        )
                    else:
                        __log__.debug(
                            'socket.timeout "%s" while reading data', e
                        )

                    raise
                except self.SocketClosed:
                    raise ConnectionResetError('Socket has closed while reading data')
                except OSError as e:
                    if e.errno != errno.EBADF:
                        # Ignore bad file descriptor while closing
                        __log__.info('OSError "%s" while reading data', e)

                    if e.errno in CONN_RESET_ERRNOS:
                        self._raise_connection_reset(e)
                    else:
                        raise

                if len(partial) == 0:
                    self._raise_connection_reset('No data on read')

                buffer.write(partial)
                bytes_left -= len(partial)

            # If everything went fine, return the read bytes
            buffer.flush()
            return buffer.raw.getvalue()

    def _raise_connection_reset(self, error):
        description = error if isinstance(error, str) else str(error)
        if isinstance(error, str):
            error = Exception(error)
        self.close()  # Connection reset -> flag as socket closed
        raise ConnectionResetError(description) from error

    # due to new https://github.com/python/cpython/pull/4386
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
