import struct
import random
import os

from .connection import Connection


class ConnectionTcpIntermediate(Connection):
    """
    Intermediate mode between `ConnectionTcpFull` and `ConnectionTcpAbridged`.
    Always sends 4 extra bytes for the packet length.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._codec = IntermediatePacket()

    def _init_conn(self):
        self._writer.write(self._codec.tag)

    def _send(self, data):
        self._writer.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self.codec.read_packet(self._reader)


class IntermediatePacket:
    tag = b'\xee\xee\xee\xee'
    mtproto_proxy_tag = tag

    def encode_packet(self, data):
        return struct.pack('<i', len(data)) + data

    async def read_packet(self, reader):
        length = struct.unpack('<i', await reader.readexactly(4))[0]
        return await reader.readexactly(length)


class RandomizedIntermediatePacket(IntermediatePacket):
    """
    Data packets are aligned to 4bytes. This codec adds random bytes of size
    from 0 to 3 bytes, which are ignored by decoder.
    """
    mtproto_proxy_tag = b'\xdd\xdd\xdd\xdd'

    def encode_packet(self, data):
        pad_size = random.randint(0, 3)
        padding = os.urandom(pad_size)
        return super().encode_packet(data + padding)

    async def read_packet(self, reader):
        packet_with_padding = await super().read_packet(reader)
        pad_size = len(packet_with_padding) % 4
        if pad_size > 0:
            return packet_with_padding[:-pad_size]
        return packet_with_padding
