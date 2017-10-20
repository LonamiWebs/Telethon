# Python rough implementation of a C# TCP client
import errno
import socket
from datetime import timedelta
from io import BytesIO, BufferedWriter
from threading import Lock


class TcpClient:
    def __init__(self, proxy=None, timeout=timedelta(seconds=5)):
        self.proxy = proxy
        self._socket = None
        self._closing_lock = Lock()

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

        self._socket.settimeout(self.timeout)

    def connect(self, ip, port):
        """Connects to the specified IP and port number.
           'timeout' must be given in seconds
        """
        if ':' in ip:  # IPv6
            mode, address = socket.AF_INET6, (ip, port, 0, 0)
        else:
            mode, address = socket.AF_INET, (ip, port)

        while True:
            try:
                while not self._socket:
                    self._recreate_socket(mode)

                self._socket.connect(address)
                break  # Successful connection, stop retrying to connect
            except OSError as e:
                # There are some errors that we know how to handle, and
                # the loop will allow us to retry
                if e.errno == errno.EBADF:
                    # Bad file descriptor, i.e. socket was closed, set it
                    # to none to recreate it on the next iteration
                    self._socket = None
                else:
                    raise

    def _get_connected(self):
        return self._socket is not None

    connected = property(fget=_get_connected)

    def close(self):
        """Closes the connection"""
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
        """Writes (sends) the specified bytes to the connected peer"""
        if self._socket is None:
            raise ConnectionResetError()

        # TODO Timeout may be an issue when sending the data, Changed in v3.5:
        # The socket timeout is now the maximum total duration to send all data.
        try:
            self._socket.sendall(data)
        except socket.timeout as e:
            raise TimeoutError() from e
        except BrokenPipeError:
            self._raise_connection_reset()
        except OSError as e:
            if e.errno == errno.EBADF:
                self._raise_connection_reset()
            else:
                raise

    def read(self, size):
        """Reads (receives) a whole block of 'size bytes
           from the connected peer.

           A timeout can be specified, which will cancel the operation if
           no data has been read in the specified time. If data was read
           and it's waiting for more, the timeout will NOT cancel the
           operation. Set to None for no timeout
        """
        if self._socket is None:
            raise ConnectionResetError()

        # TODO Remove the timeout from this method, always use previous one
        with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
            bytes_left = size
            while bytes_left != 0:
                try:
                    partial = self._socket.recv(bytes_left)
                except socket.timeout as e:
                    raise TimeoutError() from e
                except OSError as e:
                    if e.errno == errno.EBADF or e.errno == errno.ENOTSOCK:
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
