# Python rough implementation of a C# TCP client
import socket
import time
import os
from datetime import datetime, timedelta
from io import BytesIO, BufferedWriter
from threading import Event, Lock
import errno

from ..crypto import AESModeCTR
from ..errors import ReadCancelledError


# Obfuscated messages secrets cannot start with any of these
OBFUSCATED_ANTI_KEYWORDS = (b'PVrG', b'GET ', b'POST', b'\xee' * 4)


class TcpClientObfuscated:
    # TODO Avoid duplicating so much code - transport for TCPO

    def __init__(self, proxy=None):
        self.connected = False
        self._proxy = proxy
        self._recreate_socket()

        # Support for multi-threading advantages and safety
        self.cancelled = Event()  # Has the read operation been cancelled?
        self.delay = 0.1  # Read delay when there was no data available
        self._lock = Lock()

        self.aes_encrypt = None
        self.aes_decrypt = None

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

            # TCP Obfuscated bits
            while True:
                random = os.urandom(64)
                if (random[0] != b'\xef' and
                    random[:4] not in OBFUSCATED_ANTI_KEYWORDS and
                        random[4:4] != b'\0\0\0\0'):
                    # Invalid random generated
                    break

            random = list(random)
            random[56] = random[57] = random[58] = random[59] = 0xef
            random_reversed = random[55:7:-1]  # Reversed (8, len=48)

            # encryption has "continuous buffer" enabled
            encrypt_key = bytes(random[8:40])
            encrypt_iv = bytes(random[40:56])
            decrypt_key = bytes(random_reversed[:32])
            decrypt_iv = bytes(random_reversed[32:48])

            self.aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
            self.aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

            random[56:64] = self.aes_encrypt.encrypt(bytes(random))[56:64]
            self._socket.sendall(bytes(random))

    def close(self):
        """Closes the connection"""
        if self.connected:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
            except OSError as e:
                if e.errno != errno.ENOTCONN:
                    raise

            self.connected = False
            self._recreate_socket()

    def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""
        data = self.aes_encrypt.encrypt(data)

        # Ensure that only one thread can send data at once
        with self._lock:
            try:
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
            except BrokenPipeError:
                self.close()
                raise

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
            start_time = datetime.now() if timeout is not None else None

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
                            self.close()
                            raise ConnectionResetError(
                                'The server has closed the connection.')

                        buffer.write(partial)
                        bytes_left -= len(partial)

                    except BlockingIOError as error:
                        # No data available yet, sleep a bit
                        time.sleep(self.delay)

                        # Check if the timeout finished
                        if timeout is not None:
                            time_passed = datetime.now() - start_time
                            if time_passed > timeout:
                                raise TimeoutError(
                                    'The read operation exceeded the timeout.') from error

                # If everything went fine, return the read bytes
                buffer.flush()
                return self.aes_decrypt.encrypt(buffer.raw.getvalue())

    def cancel_read(self):
        """Cancels the read operation IF it hasn't yet
           started, raising a ReadCancelledError"""
        self.cancelled.set()
