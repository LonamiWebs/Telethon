# Python rough implementation of a C# TCP client
import asyncio
import errno
import socket
import logging
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


class TcpClient:
    class SocketClosed(ConnectionError):
        pass

    def __init__(self, proxy=None, timeout=timedelta(seconds=5), loop=None):
        self.proxy = proxy
        self._socket = None
        self._loop = loop if loop else asyncio.get_event_loop()
        self._logger = logging.getLogger(__name__)
        self._closed = asyncio.Event(loop=self._loop)
        self._closed.set()

        if isinstance(timeout, timedelta):
            self.timeout = timeout.seconds
        elif isinstance(timeout, (int, float)):
            self.timeout = float(timeout)
        else:
            raise ValueError('Invalid timeout type', type(timeout))

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
        """Connects to the specified IP and port number.
           'timeout' must be given in seconds
        """
        if ':' in ip:  # IPv6
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
        return not self._closed.is_set()

    connected = property(fget=_get_connected)

    def close(self):
        """Closes the connection"""
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
        done, _ = await asyncio.wait(
            [coro, self._closed.wait()],
            timeout=self.timeout,
            return_when=asyncio.FIRST_COMPLETED,
            loop=self._loop
        )
        if not self.connected:
            raise self.SocketClosed()
        if not done:
            raise TimeoutError()
        return await done.pop()

    async def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""
        if not self.connected:
            raise ConnectionResetError('No connection')
        try:
            await self._wait_close(self.sock_sendall(data))
        except self.SocketClosed:
            raise ConnectionResetError('Socket has closed')
        except OSError as e:
            if e.errno in CONN_RESET_ERRNOS:
                self._raise_connection_reset(e)
            else:
                raise

    async def read(self, size):
        """Reads (receives) a whole block of size bytes
           from the connected peer.
        """
        with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
            bytes_left = size
            while bytes_left != 0:
                if not self.connected:
                    raise ConnectionResetError('No connection')
                try:
                    partial = await self._wait_close(self.sock_recv(bytes_left))
                except self.SocketClosed:
                    raise ConnectionResetError('Socket has closed')
                except OSError as e:
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
