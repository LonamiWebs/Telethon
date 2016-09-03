# Python rough implementation of a C# TCP client
import socket


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
        self.socket.send(data)

    def read(self, buffer_size):
        """Reads (receives) the specified bytes from the connected peer"""
        return self.socket.recv(buffer_size)
