# Python rough implementation of a C# TCP client
import socket
import time
from datetime import datetime, timedelta
from io import BytesIO, BufferedWriter
from threading import Event, Lock

from ..errors import ReadCancelledError


class TcpClient:
    def __init__(self, proxy=None):
        self.connected = False
        self._proxy = proxy
        self._recreate_socket()

        # Support for multi-threading advantages and safety
        self.cancelled = Event()  # Has the read operation been cancelled?
        self.delay = 0.1  # Read delay when there was no data available
        self._lock = Lock()

    def _recreate_socket(self):
        if self._proxy is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            import socks
            self._socket = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
            if type(self._proxy) is dict:
                self._socket.set_proxy(**self._proxy)
            else:  # tuple, list, etc.
                self._socket.set_proxy(*self._proxy)

    def connect(self, ip, port):
        """Connects to the specified IP and port number"""
        if not self.connected:
            self._socket.connect((ip, port))
            self._socket.setblocking(False)
            self.connected = True

    def close(self):
        """Closes the connection"""
        if self.connected:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self.connected = False
            self._recreate_socket()

    def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""

        # Ensure that only one thread can send data at once
        with self._lock:
            view = memoryview(data)
            total_sent, total = 0, len(data)
            while total_sent < total:
                try:
                    sent = self._socket.send(view[total_sent:])
                    if sent == 0:
                        raise ConnectionResetError(
                            'The server has closed the connection.')
                    total_sent += sent

                except BlockingIOError:
                    time.sleep(self.delay)

    def read(self, size, timeout=timedelta(seconds=5)):
        """Reads (receives) a whole block of 'size bytes
           from the connected peer.

           A timeout can be specified, which will cancel the operation if
           no data has been read in the specified time. If data was read
           and it's waiting for more, the timeout will NOT cancel the
           operation. Set to None for no timeout
        """

        # Ensure that only one thread can receive data at once
        with self._lock:
            # Ensure it is not cancelled at first, so we can enter the loop
            self.cancelled.clear()

            # Set the starting time so we can
            # calculate whether the timeout should fire
            start_time = datetime.now() if timeout else None

            with BufferedWriter(BytesIO(), buffer_size=size) as buffer:
                bytes_left = size
                while bytes_left != 0:
                    # Only do cancel if no data was read yet
                    # Otherwise, carry on reading and finish
                    if self.cancelled.is_set() and bytes_left == size:
                        raise ReadCancelledError()

                    try:
                        partial = self._socket.recv(bytes_left)
                        if len(partial) == 0:
                            raise ConnectionResetError(
                                'The server has closed the connection (recv() returned 0 bytes).')

                        buffer.write(partial)
                        bytes_left -= len(partial)

                    except BlockingIOError as error:
                        # No data available yet, sleep a bit
                        time.sleep(self.delay)

                        # Check if the timeout finished
                        if timeout:
                            time_passed = datetime.now() - start_time
                            if time_passed > timeout:
                                raise TimeoutError(
                                    'The read operation exceeded the timeout.') from error

                # If everything went fine, return the read bytes
                buffer.flush()
                return buffer.raw.getvalue()

    def cancel_read(self):
        """Cancels the read operation IF it hasn't yet
           started, raising a ReadCancelledError"""
        self.cancelled.set()
