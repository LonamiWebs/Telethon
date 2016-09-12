from network import TcpClient
from binascii import crc32
from errors import *
from utils import BinaryWriter


class TcpTransport:
    def __init__(self, ip_address, port):
        self.tcp_client = TcpClient()
        self.send_counter = 0

        self.tcp_client.connect(ip_address, port)

    # Original reference: https://core.telegram.org/mtproto#tcp-transport
    # The packets are encoded as: total length, sequence number, packet and checksum (CRC32)
    def send(self, packet):
        """Sends the given packet (bytes array) to the connected peer"""
        if not self.tcp_client.connected:
            raise ConnectionError('Client not connected to server.')

        with BinaryWriter() as writer:
            writer.write_int(len(packet) + 12)  # 12 = size_of (integer) * 3
            writer.write_int(self.send_counter)
            writer.write(packet)

            crc = crc32(writer.get_bytes())
            writer.write_int(crc, signed=False)

            self.tcp_client.write(writer.get_bytes())
            self.send_counter += 1

    def receive(self):
        """Receives a TCP message (tuple(sequence number, body)) from the connected peer"""

        # First read everything we need
        packet_length_bytes = self.tcp_client.read(4)
        packet_length = int.from_bytes(packet_length_bytes, byteorder='little')

        seq_bytes = self.tcp_client.read(4)
        seq = int.from_bytes(seq_bytes, byteorder='little')

        body = self.tcp_client.read(packet_length - 12)

        checksum = int.from_bytes(self.tcp_client.read(4), byteorder='little', signed=False)

        # Then perform the checks
        rv = packet_length_bytes + seq_bytes + body
        valid_checksum = crc32(rv)

        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        # If we passed the tests, we can then return a valid TCP message
        return seq, body

    def close(self):
        if self.tcp_client.connected:
            self.tcp_client.close()

    def cancel_receive(self):
        """Cancels (stops) trying to receive from the
        remote peer and raises a ReadCancelledError"""
        self.tcp_client.cancel_read()

    def get_client_delay(self):
        """Gets the client read delay"""
        return self.tcp_client.delay
