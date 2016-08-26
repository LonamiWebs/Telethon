from zlib import crc32

from network.tcp_message import TcpMessage
from network.tcp_client import TcpClient


class TcpTransport:

    def __init__(self, ip_address, port):
        self._tcp_client = TcpClient()
        self._send_counter = 0

        self._tcp_client.connect(ip_address, port)

    def send(self, packet):
        """
        :param packet: Bytes array representing the packet to be sent
        """
        if not self._tcp_client.connected:
            raise ConnectionError('Client not connected to server.')

        tcp_message = TcpMessage(self._send_counter, packet)

        # TODO async? and receive too, of course
        self._tcp_client.write(tcp_message.encode())

        self._send_counter += 1

    def receive(self):
        # First read everything
        packet_length_bytes = self._tcp_client.read(4)
        packet_length = int.from_bytes(packet_length_bytes, byteorder='big')

        seq_bytes = self._tcp_client.read(4)
        seq = int.from_bytes(seq_bytes, byteorder='big')

        body = self._tcp_client.read(packet_length - 12)

        checksum = int.from_bytes(self._tcp_client.read(4), byteorder='big')

        # Then perform the checks
        rv = packet_length_bytes + seq_bytes + body
        valid_checksum = crc32(rv) & 0xFFFFFFFF  # Ensure it's unsigned (http://stackoverflow.com/a/30092291/4759433)

        if checksum != valid_checksum:
            raise ValueError('Invalid checksum, skip')

        return TcpMessage(seq, body)

    def dispose(self):
        if self._tcp_client.connected:
            self._tcp_client.close()
