import socket


class TcpClient:

    def __init__(self):
        self.connected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, ip, port):
        self.socket.connect((ip, port))

    def close(self):
        self.socket.close()

    def write(self, data):
        self.socket.send(data)

    def read(self, buffer_size):
        self.socket.recv(buffer_size)
