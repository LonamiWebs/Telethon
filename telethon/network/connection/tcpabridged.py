import struct

from .connection import Connection


class ConnectionTcpAbridged(Connection):
    """
    This is the mode with the lowest overhead, as it will
    only require 1 byte if the packet length is less than
    508 bytes (127 << 2, which is very common).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._codec = AbridgedPacket()

    def _init_conn(self):
        self._writer.write(self._codec.tag)

    def _send(self, data):
        self._writer.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._reader)


class AbridgedPacket:
    tag = b'\xef'
    mtproto_proxy_tag = b'\xef\xef\xef\xef'

    def encode_packet(self, data):
        length = len(data) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')
        return length + data

    async def read_packet(self, reader):
        length = struct.unpack('<B', await reader.readexactly(1))[0]
        if length >= 127:
            length = struct.unpack(
                '<i', await reader.readexactly(3) + b'\0')[0]

        return await reader.readexactly(length << 2)
