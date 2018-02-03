"""
This module holds a rough implementation of the C# TCP client.
"""
import errno
import socket
import time
from datetime import timedelta
from io import BytesIO, BufferedWriter
from threading import Lock

MAX_TIMEOUT = 15  # in seconds
CONN_RESET_ERRNOS = {
    errno.EBADF, errno.ENOTSOCK, errno.ENETUNREACH,
    errno.EINVAL, errno.ENOTCONN
}


class TcpClient:
    """A simple TCP client to ease the work with sockets and proxies."""
    def __init__(self, proxy=None, timeout=timedelta(seconds=5)):
        """
        Initializes the TCP client.

        :param proxy: the proxy to be used, if any.
        :param timeout: the timeout for connect, read and write operations.
        """
        self.proxy = proxy
        self._socket = None
        self._closing_lock = Lock()

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

        self._socket.settimeout(self.timeout)

    def connect(self, ip, port):
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

        timeout = 1
        while True:
            try:
                while not self._socket:
                    self._recreate_socket(mode)

                self._socket.connect(address)
                break  # Successful connection, stop retrying to connect
            except OSError as e:
                # There are some errors that we know how to handle, and
                # the loop will allow us to retry
                if e.errno in (errno.EBADF, errno.ENOTSOCK, errno.EINVAL,
                               errno.ECONNREFUSED,  # Windows-specific follow
                               getattr(errno, 'WSAEACCES', None)):
                    # Bad file descriptor, i.e. socket was closed, set it
                    # to none to recreate it on the next iteration
                    self._socket = None
                    time.sleep(timeout)
                    timeout = min(timeout * 2, MAX_TIMEOUT)
                else:
                    raise

    def _get_connected(self):
        """Determines whether the client is connected or not."""
        return self._socket is not None and self._socket.fileno() >= 0

    connected = property(fget=_get_connected)

    def close(self):
        """Closes the connection."""
        if self._closing_lock.locked():
            # Already closing, no need to close again (avoid None.close())
            return

        with self._closing_lock:
            try:
                if self._socket is not None:
                    self._socket.shutdown(socket.SHUT_RDWR)
                    self._socket.close()
            except OSError:
                pass  # Ignore ENOTCONN, EBADF, and any other error when closing
            finally:
                self._socket = None

    def write(self, data):
        """
        Writes (sends) the specified bytes to the connected peer.

        :param data: the data to send.
        """
        if self._socket is None:
            self._raise_connection_reset()

        # TODO Timeout may be an issue when sending the data, Changed in v3.5:
        # The socket timeout is now the maximum total duration to send all data.
        try:
            self._socket.sendall(data)
        except socket.timeout as e:
            raise TimeoutError() from e
        except ConnectionError:
            self._raise_connection_reset()
        except OSError as e:
            if e.errno in CONN_RESET_ERRNOS:
                self._raise_connection_reset()
            else:
                raise

    def read(self, size):
        """
        Reads (receives) a whole block of size bytes from the connected peer.

        :param size: the size of the block to be read.
        :return: the read data with len(data) == size.
        """
        if self._socket is None:
            self._raise_connection_reset()

        # TODO Remove the timeout from this method, always use previous one
        with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
            bytes_left = size
            while bytes_left != 0:
                try:
                    partial = self._socket.recv(bytes_left)
                except socket.timeout as e:
                    raise TimeoutError() from e
                except ConnectionError:
                    self._raise_connection_reset()
                except OSError as e:
                    if e.errno in CONN_RESET_ERRNOS:
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
        """Disconnects the client and raises ConnectionResetError."""
        self.close()  # Connection reset -> flag as socket closed
        raise ConnectionResetError('The server has closed the connection.')
