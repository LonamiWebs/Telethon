# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Network/TcpTransport.cs
from zlib import crc32
from network.tcp_message import TcpMessage
from network.tcp_client import TcpClient


class TcpTransport:
    def __init__(self, ip_address, port):
        self._tcp_client = TcpClient()
        self._send_counter = 0

        self._tcp_client.connect(ip_address, port)

    def send(self, packet):
        """Sends the given packet (bytes array) to the connected peer"""
        if not self._tcp_client.connected:
            raise ConnectionError('Client not connected to server.')

        # Get a TcpMessage which contains the given packet
        tcp_message = TcpMessage(self._send_counter, packet)

        # TODO In TLSharp, this is async; Should both send and receive be here too?
        self._tcp_client.write(tcp_message.encode())
        self._send_counter += 1

    def receive(self):
        """Receives a TcpMessage from the connected peer"""

        # First read everything
        packet_length_bytes = self._tcp_client.read(4)
        packet_length = int.from_bytes(packet_length_bytes, byteorder='little')

        seq_bytes = self._tcp_client.read(4)
        seq = int.from_bytes(seq_bytes, byteorder='little')

        body = self._tcp_client.read(packet_length - 12)

        checksum = int.from_bytes(self._tcp_client.read(4), byteorder='little')

        # Then perform the checks
        rv = packet_length_bytes + seq_bytes + body
        # Ensure it's unsigned (http://stackoverflow.com/a/30092291/4759433)
        valid_checksum = crc32(rv) & 0xFFFFFFFF

        if checksum != valid_checksum:
            raise ValueError('Invalid checksum, skip')

        # If we passed the tests, we can then return a valid TcpMessage
        return TcpMessage(seq, body)

    def dispose(self):
        if self._tcp_client.connected:
            self._tcp_client.close()
