import errno
import os
import struct
from datetime import timedelta
from enum import Enum
from zlib import crc32

from ..crypto import AESModeCTR
from ..errors import InvalidChecksumError
from ..extensions import TcpClient


class ConnectionMode(Enum):
    """Represents which mode should be used to stabilise a connection.

    TCP_FULL: Default Telegram mode. Sends 12 additional bytes and
              needs to calculate the CRC value of the packet itself.

    TCP_INTERMEDIATE: Intermediate mode between TCP_FULL and TCP_ABRIDGED.
                      Always sends 4 extra bytes for the packet length.

    TCP_ABRIDGED: This is the mode with the lowest overhead, as it will
                  only require 1 byte if the packet length is less than
                  508 bytes (127 << 2, which is very common).

    TCP_OBFUSCATED: Encodes the packet just like TCP_ABRIDGED, but encrypts
                    every message with a randomly generated key using the
                    AES-CTR mode so the packets are harder to discern.
    """
    TCP_FULL = 1
    TCP_INTERMEDIATE = 2
    TCP_ABRIDGED = 3
    TCP_OBFUSCATED = 4


class Connection:
    """Represents an abstract connection (TCP, TCP abridged...).
       'mode' must be any of the ConnectionMode enumeration.

       Note that '.send()' and '.recv()' refer to messages, which
       will be packed accordingly, whereas '.write()' and '.read()'
       work on plain bytes, with no further additions.
    """

    def __init__(self, mode=ConnectionMode.TCP_FULL,
                 proxy=None, timeout=timedelta(seconds=5), loop=None):
        self._mode = mode
        self._send_counter = 0
        self._aes_encrypt, self._aes_decrypt = None, None

        # TODO Rename "TcpClient" as some sort of generic socket?
        self.conn = TcpClient(proxy=proxy, timeout=timeout, loop=loop)

        # Sending messages
        if mode == ConnectionMode.TCP_FULL:
            setattr(self, 'send', self._send_tcp_full)
            setattr(self, 'recv', self._recv_tcp_full)

        elif mode == ConnectionMode.TCP_INTERMEDIATE:
            setattr(self, 'send', self._send_intermediate)
            setattr(self, 'recv', self._recv_intermediate)

        elif mode in (ConnectionMode.TCP_ABRIDGED,
                      ConnectionMode.TCP_OBFUSCATED):
            setattr(self, 'send', self._send_abridged)
            setattr(self, 'recv', self._recv_abridged)

        # Writing and reading from the socket
        if mode == ConnectionMode.TCP_OBFUSCATED:
            setattr(self, 'write', self._write_obfuscated)
            setattr(self, 'read', self._read_obfuscated)
        else:
            setattr(self, 'write', self._write_plain)
            setattr(self, 'read', self._read_plain)

    async def connect(self, ip, port):
        try:
            await self.conn.connect(ip, port)
        except OSError as e:
            if e.errno == errno.EISCONN:
                return  # Already connected, no need to re-set everything up
            else:
                raise

        self._send_counter = 0
        if self._mode == ConnectionMode.TCP_ABRIDGED:
            await self.conn.write(b'\xef')
        elif self._mode == ConnectionMode.TCP_INTERMEDIATE:
            await self.conn.write(b'\xee\xee\xee\xee')
        elif self._mode == ConnectionMode.TCP_OBFUSCATED:
            await self._setup_obfuscation()

    def get_timeout(self):
        return self.conn.timeout

    async def _setup_obfuscation(self):
        # Obfuscated messages secrets cannot start with any of these
        keywords = (b'PVrG', b'GET ', b'POST', b'\xee' * 4)
        while True:
            random = os.urandom(64)
            if (random[0] != b'\xef' and
                    random[:4] not in keywords and
                    random[4:4] != b'\0\0\0\0'):
                # Invalid random generated
                break

        random = list(random)
        random[56] = random[57] = random[58] = random[59] = 0xef
        random_reversed = random[55:7:-1]  # Reversed (8, len=48)

        # encryption has "continuous buffer" enabled
        encrypt_key = bytes(random[8:40])
        encrypt_iv = bytes(random[40:56])
        decrypt_key = bytes(random_reversed[:32])
        decrypt_iv = bytes(random_reversed[32:48])

        self._aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
        self._aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:64] = self._aes_encrypt.encrypt(bytes(random))[56:64]
        await self.conn.write(bytes(random))

    def is_connected(self):
        return self.conn.connected

    def close(self):
        self.conn.close()

    def clone(self):
        """Creates a copy of this Connection"""
        return Connection(
            mode=self._mode, proxy=self.conn.proxy, timeout=self.conn.timeout
        )

    # region Receive message implementations

    async def recv(self):
        """Receives and unpacks a message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    async def _recv_tcp_full(self):
        # TODO We don't want another call to this method that could
        # potentially await on another self.read(n). Is this guaranteed
        # by asyncio?
        packet_len_seq = await self.read(8)  # 4 and 4
        packet_len, seq = struct.unpack('<ii', packet_len_seq)

        body = await self.read(packet_len - 12)
        checksum = struct.unpack('<I', await self.read(4))[0]

        valid_checksum = crc32(packet_len_seq + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body

    async def _recv_intermediate(self):
        return await self.read(struct.unpack('<i', await self.read(4))[0])

    async def _recv_abridged(self):
        length = struct.unpack('<B', await self.read(1))[0]
        if length >= 127:
            length = struct.unpack('<i', await self.read(3) + b'\0')[0]

        return await self.read(length << 2)

    # endregion

    # region Send message implementations

    async def send(self, message):
        """Encapsulates and sends the given message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    async def _send_tcp_full(self, message):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        length = len(message) + 12
        data = struct.pack('<ii', length, self._send_counter) + message
        crc = struct.pack('<I', crc32(data))
        self._send_counter += 1
        await self.write(data + crc)

    async def _send_intermediate(self, message):
        await self.write(struct.pack('<i', len(message)) + message)

    async def _send_abridged(self, message):
        length = len(message) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        await self.write(length + message)

    # endregion

    # region Read implementations

    async def read(self, length):
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    async def _read_plain(self, length):
        return await self.conn.read(length)

    async def _read_obfuscated(self, length):
        return self._aes_decrypt.encrypt(await self.conn.read(length))

    # endregion

    # region Write implementations

    async def write(self, data):
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    async def _write_plain(self, data):
        await self.conn.write(data)

    async def _write_obfuscated(self, data):
        await self.conn.write(self._aes_encrypt.encrypt(data))

    # endregion
