# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/Network/TcpMessage.cs
from utils import BinaryWriter, BinaryReader
from binascii import crc32
from errors import *


class TcpMessage:
    def __init__(self, seq_number, body):
        """
        :param seq_number: Sequence number
        :param body: Message body byte array
        """
        if body is None:
            raise InvalidParameterError('body cannot be None')

        self.sequence_number = seq_number
        self.body = body

    def encode(self):
        """Returns the bytes of the this message encoded, following Telegram's guidelines"""
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

            crc = crc32(writer.get_bytes())
            writer.write_int(crc, signed=False)

            return writer.get_bytes()

    @staticmethod
    def decode(body):
        """Returns a TcpMessage from the given encoded bytes, decoding them previously"""
        if body is None:
            raise InvalidParameterError('body cannot be None')

        if len(body) < 12:
            raise InvalidParameterError('Wrong size of input packet')

        with BinaryReader(body) as reader:
            packet_len = int.from_bytes(reader.read(4), byteorder='little')
            if packet_len < 12:
                raise InvalidParameterError('Invalid packet length in body: {}'.format(packet_len))

            seq = reader.read_int()
            packet = reader.read(packet_len - 12)
            checksum = reader.read_int(signed=False)

            valid_checksum = crc32(body[:packet_len - 4])
            if checksum != valid_checksum:
                raise InvalidChecksumError(checksum, valid_checksum)

            return TcpMessage(seq, packet)
