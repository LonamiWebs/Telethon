import struct

from .tcpfull import ConnectionTcpFull


class ConnectionTcpIntermediate(ConnectionTcpFull):
    """
    Intermediate mode between `ConnectionTcpFull` and `ConnectionTcpAbridged`.
    Always sends 4 extra bytes for the packet length.
    """
    def connect(self, ip, port):
        result = super().connect(ip, port)
        self.conn.write(b'\xee\xee\xee\xee')
        return result

    def clone(self):
        return ConnectionTcpIntermediate(self._proxy, self._timeout)

    def recv(self):
        return self.read(struct.unpack('<i', self.read(4))[0])

    def send(self, message):
        self.write(struct.pack('<i', len(message)) + message)
