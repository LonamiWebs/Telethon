import struct

from .tcpfull import ConnectionTcpFull


class ConnectionTcpAbridged(ConnectionTcpFull):
    """
    This is the mode with the lowest overhead, as it will
    only require 1 byte if the packet length is less than
    508 bytes (127 << 2, which is very common).
    """
    def connect(self, ip, port):
        result = super().connect(ip, port)
        self.conn.write(b'\xef')
        return result

    def clone(self):
        return ConnectionTcpAbridged(self._proxy, self._timeout)

    def recv(self):
        length = struct.unpack('<B', self.read(1))[0]
        if length >= 127:
            length = struct.unpack('<i', self.read(3) + b'\0')[0]

        return self.read(length << 2)

    def send(self, message):
        length = len(message) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        self.write(length + message)
