# Python rough implementation of a C# TCP client
import socket
from utils import BinaryWriter


class TcpClient:
    def __init__(self):
        self.connected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, ip, port):
        """Connects to the specified IP and port number"""
        self.socket.connect((ip, port))
        self.connected = True

    def close(self):
        """Closes the connection"""
        self.socket.close()
        self.connected = False

    def write(self, data):
        """Writes (sends) the specified bytes to the connected peer"""
        self.socket.sendall(data)

    def read(self, buffer_size):
        """Reads (receives) the specified bytes from the connected peer"""
        with BinaryWriter() as writer:
            while writer.written_count < buffer_size:
                # When receiving from the socket, we may not receive all the data at once
                # This is why we need to keep checking to make sure that we receive it all
                left_count = buffer_size - writer.written_count
                partial = self.socket.recv(left_count)
                writer.write(partial)

            return writer.get_bytes()
