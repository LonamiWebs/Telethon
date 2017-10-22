# Python rough implementation of a C# TCP client
import asyncio
import errno
import socket
from datetime import timedelta
from io import BytesIO, BufferedWriter


class TcpClient:
    def __init__(self, proxy=None, timeout=timedelta(seconds=5), loop=None):
        self.proxy = proxy
        self._socket = None
        self._loop = loop if loop else asyncio.get_event_loop()

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

        timeout = 1
        while True:
            try:
                if not self._socket:
                    self._recreate_socket(mode)

                await self._loop.sock_connect(self._socket, address)
                break  # Successful connection, stop retrying to connect
            except ConnectionError:
                self._socket = None
                await asyncio.sleep(min(timeout, 15))
                timeout *= 2
            except OSError as e:
                # There are some errors that we know how to handle, and
                # the loop will allow us to retry
                if e.errno in [errno.EBADF, errno.ENOTSOCK, errno.EINVAL]:
                    # Bad file descriptor, i.e. socket was closed, set it
                    # to none to recreate it on the next iteration
                    self._socket = None
                    await asyncio.sleep(min(timeout, 15))
                    timeout *= 2
                else:
                    raise

    def _get_connected(self):
        return self._socket is not None

    connected = property(fget=_get_connected)

    def close(self):
        """Closes the connection"""
        try:
            if self._socket is not None:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
        except OSError:
            pass  # Ignore ENOTCONN, EBADF, and any other error when closing
        finally:
            self._socket = None

    async def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""
        if self._socket is None:
            raise ConnectionResetError()

        try:
            await asyncio.wait_for(self._loop.sock_sendall(self._socket, data),
                                   timeout=self.timeout, loop=self._loop)
        except asyncio.TimeoutError as e:
            raise TimeoutError() from e
        except BrokenPipeError:
            self._raise_connection_reset()
        except OSError as e:
            if e.errno in [errno.EBADF, errno.ENOTSOCK, errno.ENETUNREACH, errno.EINVAL, errno.ENOTCONN]:
                self._raise_connection_reset()
            else:
                raise

    async def read(self, size):
        """Reads (receives) a whole block of 'size bytes
           from the connected peer.
        """
        if self._socket is None:
            raise ConnectionResetError()

        # TODO Remove the timeout from this method, always use previous one
        with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
            bytes_left = size
            while bytes_left != 0:
                try:
                    partial = await asyncio.wait_for(self._loop.sock_recv(self._socket, bytes_left),
                                                     timeout=self.timeout, loop=self._loop)
                except asyncio.TimeoutError as e:
                    raise TimeoutError() from e
                except OSError as e:
                    if e.errno in [errno.EBADF, errno.ENOTSOCK, errno.ENETUNREACH, errno.EINVAL, errno.ENOTCONN]:
                        self._raise_connection_reset()
                    else:
                        raise

                if len(partial) == 0:
                    self._raise_connection_reset()

                buffer.write(partial)
                bytes_left -= len(partial)

            # If everything went fine, return the read bytes
            buffer.flush()
            return buffer.raw.getvalue()

    def _raise_connection_reset(self):
        self.close()  # Connection reset -> flag as socket closed
        raise ConnectionResetError('The server has closed the connection.')
