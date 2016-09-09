# Python rough implementation of a C# TCP client
import socket
import time

from errors import ReadCancelledError
from utils import BinaryWriter


class TcpClient:
    def __init__(self):
        self.connected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.cancelled = False  # Has the read operation been cancelled?
        self.delay = 0.1  # Read delay when there was no data available

    def connect(self, ip, port):
        """Connects to the specified IP and port number"""
        self.socket.connect((ip, port))
        self.connected = True
        self.socket.setblocking(False)

    def close(self):
        """Closes the connection"""
        self.socket.close()
        self.connected = False
        self.socket.setblocking(True)

    def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""
        self.socket.sendall(data)

    def read(self, buffer_size):
        """Reads (receives) the specified bytes from the connected peer"""
        self.cancelled = False  # Ensure it is not cancelled at first

        with BinaryWriter() as writer:
            while writer.written_count < buffer_size and not self.cancelled:
                try:
                    # When receiving from the socket, we may not receive all the data at once
                    # This is why we need to keep checking to make sure that we receive it all
                    left_count = buffer_size - writer.written_count
                    partial = self.socket.recv(left_count)
                    writer.write(partial)

                except BlockingIOError:
                    # There was no data available for us to read. Sleep a bit
                    time.sleep(self.delay)

            # If the operation was cancelled *but* data was read,
            # this will result on data loss so raise an exception
            # TODO this could be solved by using an internal FIFO buffer (first in, first out)
            if self.cancelled:
                if writer.written_count == 0:
                    raise ReadCancelledError()
                else:
                    raise NotImplementedError('The read operation was cancelled when some data '
                                              'was already read. This has not yet implemented '
                                              'an internal buffer, so cannot continue.')

            return writer.get_bytes()

    def cancel_read(self):
        """Cancels the read operation if it was blocking and stops
           the current thread until it's cancelled"""
        self.cancelled = True
        time.sleep(self.delay)
