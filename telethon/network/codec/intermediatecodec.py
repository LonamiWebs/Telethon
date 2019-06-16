import struct
import random
import os

from .basecodec import BaseCodec


class IntermediateCodec(BaseCodec):
    """
    Intermediate mode between `FullCodec` and `AbridgedCodec`.
    Always sends 4 extra bytes for the packet length.
    """
    @staticmethod
    def header_length():
        return 4

    @staticmethod
    def tag():
        return b'\xee\xee\xee\xee'  # same as obfuscate tag

    def encode_packet(self, data, ip, port):
        return struct.pack('<i', len(data)) + data

    def decode_header(self, header):
        return struct.unpack('<i', header)[0]


class RandomizedIntermediateCodec(IntermediateCodec):
    """
    Data packets are aligned to 4 bytes. This codec adds random
    bytes of size from 0 to 3 bytes, which are ignored by decoder.
    """
    tag = None
    obfuscate_tag = b'\xdd\xdd\xdd\xdd'

    def encode_packet(self, data, ip, port):
        pad_size = random.randint(0, 3)
        padding = os.urandom(pad_size)
        return super().encode_packet(data + padding)

    async def read_packet(self, reader):
        raise NotImplementedError(':)')
        packet_with_padding = await super().read_packet(reader)
        pad_size = len(packet_with_padding) % 4
        if pad_size > 0:
            return packet_with_padding[:-pad_size]
        return packet_with_padding
