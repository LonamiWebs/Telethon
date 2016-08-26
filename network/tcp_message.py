
from zlib import crc32

from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader


class TcpMessage:

    def __init__(self, seq_number, body):
        """
        :param seq_number: Sequence number
        :param body: Message body byte array
        """
        if body is None:
            raise ValueError('body cannot be None')

        self.sequence_number = seq_number
        self.body = body

    def encode(self):
        with BinaryWriter() as writer:
            ''' https://core.telegram.org/mtproto#tcp-transport

                4 length bytes are added at the front
                (to include the length, the sequence number, and CRC32; always divisible by 4)
                and 4 bytes with the packet sequence number within this TCP connection
                (the first packet sent is numbered 0, the next one 1, etc.),
                and 4 CRC32 bytes at the end (length, sequence number, and payload together).
            '''
            writer.write_int(len(self.body) + 12)
            writer.write_int(self.sequence_number)
            writer.write(self.body)
            writer.flush()  # Flush so we can get the buffer in the CRC

            crc = crc32(writer.get_bytes()[0:8 + len(self.body)])
            writer.write_int(crc, signed=False)

            return writer.get_bytes()

    def decode(self, body):
        if body is None:
            raise ValueError('body cannot be None')

        if len(body) < 12:
            raise ValueError('Wrong size of input packet')

        with BinaryReader(body) as reader:
            packet_len = int.from_bytes(reader.read(4), byteorder='big')
            if packet_len < 12:
                raise ValueError('Invalid packet length: {}'.format(packet_len))

            seq = reader.read_int()
            packet = reader.read(packet_len - 12)
            checksum = reader.read_int()

            valid_checksum = crc32(body[:packet_len - 4])
            if checksum != valid_checksum:
                raise ValueError('Invalid checksum, skip')

            return TcpMessage(seq, packet)
