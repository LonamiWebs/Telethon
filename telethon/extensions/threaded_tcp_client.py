import socket
import time
from datetime import datetime, timedelta
from io import BytesIO, BufferedWriter
from threading import Event, Lock, Thread, Condition

from ..errors import ReadCancelledError


class ThreadedTcpClient:
    """The main difference with the TcpClient class is that this one
       will spawn a secondary thread that will be constantly reading
       from the network and putting everything on another buffer.
    """
    def __init__(self, proxy=None):
        self.connected = False
        self._proxy = proxy
        self._recreate_socket()

        # Support for multi-threading advantages and safety
        self.cancelled = Event()  # Has the read operation been cancelled?
        self.delay = 0.1  # Read delay when there was no data available
        self._lock = Lock()

        self._buffer = []
        self._read_thread = Thread(target=self._reading_thread, daemon=True)
        self._cv = Condition()  # Condition Variable

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

    def connect(self, ip, port, timeout):
        """Connects to the specified IP and port number.
           'timeout' must be given in seconds
        """
        if not self.connected:
            self._socket.settimeout(timeout)
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
        self._socket.sendall(data)

    def read(self, size, timeout=timedelta(seconds=5)):
        """Reads (receives) a whole block of 'size bytes
           from the connected peer.

           A timeout can be specified, which will cancel the operation if
           no data has been read in the specified time. If data was read
           and it's waiting for more, the timeout will NOT cancel the
           operation. Set to None for no timeout
        """
        with self._cv:
            print('wait for...')
            self._cv.wait_for(lambda: len(self._buffer) >= size, timeout=timeout.seconds)
            print('got', size)
            result, self._buffer = self._buffer[:size], self._buffer[size:]
            return result

    def _reading_thread(self):
        while True:
            partial = self._socket.recv(4096)
            if len(partial) == 0:
                self.connected = False
                raise ConnectionResetError(
                    'The server has closed the connection.')

            with self._cv:
                print('extended', len(partial))
                self._buffer.extend(partial)
                self._cv.notify()

    def cancel_read(self):
        """Cancels the read operation IF it hasn't yet
           started, raising a ReadCancelledError"""
        self.cancelled.set()
