from datetime import timedelta
from zlib import crc32

from ..extensions import BinaryWriter, TcpClient
from ..errors import InvalidChecksumError


class Connection:
    def __init__(self, ip, port, mode='tcp_abridged',
                 proxy=None, timeout=timedelta(seconds=5)):
        """Represents an abstract connection (TCP, TCP abridged...).
           'mode' may be any of 'tcp_full', 'tcp_abridged'
        """
        self.ip = ip
        self.port = port
        self._mode = mode
        self.timeout = timeout
        self._send_counter = 0

        # TODO Rename "TcpClient" as some sort of generic socket
        self.conn = TcpClient(proxy=proxy)

        if mode == 'tcp_full':
            setattr(self, 'send', self._send_tcp_full)
            setattr(self, 'recv', self._recv_tcp_full)

        elif mode == 'tcp_abridged':
            setattr(self, 'send', self._send_abridged)
            setattr(self, 'recv', self._recv_abridged)

    def connect(self):
        self._send_counter = 0
        self.conn.connect(self.ip, self.port,
                          timeout=round(self.timeout.seconds))

        if self._mode == 'tcp_abridged':
            self.conn.write(int.to_bytes(239, 1, 'little'))

    def is_connected(self):
        return self.conn.connected

    def close(self):
        self.conn.close()

    def cancel_receive(self):
        """Cancels (stops) trying to receive from the
        remote peer and raises a ReadCancelledError"""
        self.conn.cancel_read()

    def get_client_delay(self):
        """Gets the client read delay"""
        return self.conn.delay

    # region Receive implementations

    def recv(self, **kwargs):
        """Receives and unpacks a message"""
        # TODO Don't ignore kwargs['timeout']?
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _recv_tcp_full(self, **kwargs):
        packet_length_bytes = self.conn.read(4, self.timeout)
        packet_length = int.from_bytes(packet_length_bytes, 'little')

        seq_bytes = self.conn.read(4, self.timeout)
        seq = int.from_bytes(seq_bytes, 'little')

        body = self.conn.read(packet_length - 12, self.timeout)
        checksum = int.from_bytes(self.conn.read(4, self.timeout), 'little')

        valid_checksum = crc32(packet_length_bytes + seq_bytes + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body

    def _recv_abridged(self, **kwargs):
        length = int.from_bytes(self.conn.read(1, self.timeout), 'little')
        if length >= 127:
            length = int.from_bytes(self.conn.read(3, self.timeout) + b'\0', 'little')

        return self.conn.read(length << 2)

    # endregion

    # region Send implementations

    def send(self, message):
        """Encapsulates and sends the given message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _send_tcp_full(self, message):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        with BinaryWriter() as writer:
            writer.write_int(len(message) + 12)
            writer.write_int(self._send_counter)
            writer.write(message)
            writer.write_int(crc32(writer.get_bytes()), signed=False)
            self._send_counter += 1
            self.conn.write(writer.get_bytes())

    def _send_abridged(self, message):
        with BinaryWriter() as writer:
            length = len(message) >> 2
            if length < 127:
                writer.write_byte(length)
            else:
                writer.write_byte(127)
                writer.write(int.to_bytes(length, 3, 'little'))
            writer.write(message)
            self.conn.write(writer.get_bytes())

    # endregion
