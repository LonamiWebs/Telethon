# Python rough implementation of a C# TCP client
import socket
import time
from datetime import datetime, timedelta
from threading import Event, Lock

from ..errors import ReadCancelledError
from ..utils import BinaryWriter


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
            self.connected = True

    def close(self):
        """Closes the connection"""
        if self.connected:
            self._socket.close()
            self.connected = False
            self._recreate_socket()

    def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""

        # Ensure that only one thread can send data at once
        with self._lock:
            # Set blocking so it doesn't error
            self._socket.setblocking(True)
            self._socket.sendall(data)

    def read(self, buffer_size, timeout=timedelta(seconds=5)):
        """Reads (receives) the specified bytes from the connected peer.
           A timeout can be specified, which will cancel the operation if no data
           has been read in the specified time. If data was read and it's waiting
           for more, the timeout will NOT cancel the operation. Set to None for no timeout"""

        # Ensure that only one thread can receive data at once
        with self._lock:
            # Ensure it is not cancelled at first, so we can enter the loop
            self.cancelled.clear()

            # Set non-blocking so it can be cancelled
            self._socket.setblocking(False)

            # Set the starting time so we can calculate whether the timeout should fire
            if timeout:
                start_time = datetime.now()

            with BinaryWriter() as writer:
                while writer.written_count < buffer_size:
                    # Only do cancel if no data was read yet
                    # Otherwise, carry on reading and finish
                    if self.cancelled.is_set() and writer.written_count == 0:
                        raise ReadCancelledError()

                    try:
                        # When receiving from the socket, we may not receive all the data at once
                        # This is why we need to keep checking to make sure that we receive it all
                        left_count = buffer_size - writer.written_count
                        partial = self._socket.recv(left_count)
                        if len(partial) == 0:
                            raise ConnectionResetError(
                                'The server has closed the connection (recv() returned 0 bytes).')
                        writer.write(partial)

                    except BlockingIOError as error:
                        # There was no data available for us to read. Sleep a bit
                        time.sleep(self.delay)

                        # Check if the timeout finished
                        if timeout:
                            time_passed = datetime.now() - start_time
                            if time_passed > timeout:
                                raise TimeoutError(
                                    'The read operation exceeded the timeout.') from error

                # If everything went fine, return the read bytes
                return writer.get_bytes()

    def cancel_read(self):
        """Cancels the read operation IF it hasn't yet
           started, raising a ReadCancelledError"""
        self.cancelled.set()
