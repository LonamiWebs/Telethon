"""
This module holds both the Connection class and the ConnectionMode enum,
which specifies the protocol to be used by the Connection.
"""
import logging
import os
import struct
from datetime import timedelta
from zlib import crc32
from enum import Enum

import errno

from ..crypto import AESModeCTR
from ..extensions import TcpClient
from ..errors import InvalidChecksumError

__log__ = logging.getLogger(__name__)


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
    """
    Represents an abstract connection (TCP, TCP abridged...).
    'mode' must be any of the ConnectionMode enumeration.

    Note that '.send()' and '.recv()' refer to messages, which
    will be packed accordingly, whereas '.write()' and '.read()'
    work on plain bytes, with no further additions.
    """

    def __init__(self, mode=ConnectionMode.TCP_FULL,
                 proxy=None, timeout=timedelta(seconds=5)):
        """
        Initializes a new connection.

        :param mode: the ConnectionMode to be used.
        :param proxy: whether to use a proxy or not.
        :param timeout: timeout to be used for all operations.
        """
        self._mode = mode
        self._send_counter = 0
        self._aes_encrypt, self._aes_decrypt = None, None

        # TODO Rename "TcpClient" as some sort of generic socket?
        self.conn = TcpClient(proxy=proxy, timeout=timeout)

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

    def connect(self, ip, port):
        """
        Estabilishes a connection to IP:port.

        :param ip: the IP to connect to.
        :param port: the port to connect to.
        """
        try:
            self.conn.connect(ip, port)
        except OSError as e:
            if e.errno == errno.EISCONN:
                return  # Already connected, no need to re-set everything up
            else:
                raise

        self._send_counter = 0
        if self._mode == ConnectionMode.TCP_ABRIDGED:
            self.conn.write(b'\xef')
        elif self._mode == ConnectionMode.TCP_INTERMEDIATE:
            self.conn.write(b'\xee\xee\xee\xee')
        elif self._mode == ConnectionMode.TCP_OBFUSCATED:
            self._setup_obfuscation()

    def get_timeout(self):
        """Returns the timeout used by the connection."""
        return self.conn.timeout

    def _setup_obfuscation(self):
        """
        Sets up the obfuscated protocol.
        """
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
        self.conn.write(bytes(random))

    def is_connected(self):
        """
        Determines whether the connection is alive or not.

        :return: true if it's connected.
        """
        return self.conn.connected

    def close(self):
        """Closes the connection."""
        self.conn.close()

    def clone(self):
        """Creates a copy of this Connection."""
        return Connection(
            mode=self._mode, proxy=self.conn.proxy, timeout=self.conn.timeout
        )

    # region Receive message implementations

    def recv(self):
        """Receives and unpacks a message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    def _recv_tcp_full(self):
        """
        Receives a message from the network,
        internally encoded using the TCP full protocol.

        May raise InvalidChecksumError if the received data doesn't
        match its valid checksum.

        :return: the read message payload.
        """
        packet_len_seq = self.read(8)  # 4 and 4
        packet_len, seq = struct.unpack('<ii', packet_len_seq)

        # Sometimes Telegram seems to send a packet length of 0 (12)
        # and after that, just a single byte. Not sure what this is.
        # TODO Figure out what this is, and if there's a better fix.
        if packet_len <= 12:
            __log__.error('Read invalid packet length %d, '
                          'reading data left:', packet_len)
            while True:
                try:
                    __log__.error(repr(self.read(1)))
                except TimeoutError:
                    break
            # Connection reset and hope it's fixed after
            self.conn.close()
            raise ConnectionResetError()

        body = self.read(packet_len - 12)
        checksum = struct.unpack('<I', self.read(4))[0]

        valid_checksum = crc32(packet_len_seq + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body

    def _recv_intermediate(self):
        """
        Receives a message from the network,
        internally encoded using the TCP intermediate protocol.

        :return: the read message payload.
        """
        return self.read(struct.unpack('<i', self.read(4))[0])

    def _recv_abridged(self):
        """
        Receives a message from the network,
        internally encoded using the TCP abridged protocol.

        :return: the read message payload.
        """
        length = struct.unpack('<B', self.read(1))[0]
        if length >= 127:
            length = struct.unpack('<i', self.read(3) + b'\0')[0]

        return self.read(length << 2)

    # endregion

    # region Send message implementations

    def send(self, message):
        """Encapsulates and sends the given message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    def _send_tcp_full(self, message):
        """
        Encapsulates and sends the given message payload
        using the TCP full mode (length, sequence, message, crc32).

        :param message: the message to be sent.
        """
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        length = len(message) + 12
        data = struct.pack('<ii', length, self._send_counter) + message
        crc = struct.pack('<I', crc32(data))
        self._send_counter += 1
        self.write(data + crc)

    def _send_intermediate(self, message):
        """
        Encapsulates and sends the given message payload
        using the TCP intermediate mode (length, message).

        :param message: the message to be sent.
        """
        self.write(struct.pack('<i', len(message)) + message)

    def _send_abridged(self, message):
        """
        Encapsulates and sends the given message payload
        using the TCP abridged mode (short length, message).

        :param message: the message to be sent.
        """
        length = len(message) >> 2
        if length < 127:
            length = struct.pack('B', length)
        else:
            length = b'\x7f' + int.to_bytes(length, 3, 'little')

        self.write(length + message)

    # endregion

    # region Read implementations

    def read(self, length):
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    def _read_plain(self, length):
        """
        Reads data from the socket connection.

        :param length: how many bytes should be read.
        :return: a byte sequence with len(data) == length
        """
        return self.conn.read(length)

    def _read_obfuscated(self, length):
        """
        Reads data and decrypts from the socket connection.

        :param length: how many bytes should be read.
        :return: the decrypted byte sequence with len(data) == length
        """
        return self._aes_decrypt.encrypt(
            self.conn.read(length)
        )

    # endregion

    # region Write implementations

    def write(self, data):
        raise ValueError('Invalid connection mode specified: ' + str(self._mode))

    def _write_plain(self, data):
        """
        Writes the given data through the socket connection.

        :param data: the data in bytes to be written.
        """
        self.conn.write(data)

    def _write_obfuscated(self, data):
        """
        Writes the given data through the socket connection,
        using the obfuscated mode (AES encryption is applied on top).

        :param data: the data in bytes to be written.
        """
        self.conn.write(self._aes_encrypt.encrypt(data))

    # endregion
