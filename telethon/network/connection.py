import os
from datetime import timedelta
from zlib import crc32

from ..crypto import AESModeCTR
from ..extensions import BinaryWriter, TcpClient
from ..errors import InvalidChecksumError


class Connection:
    """Represents an abstract connection (TCP, TCP abridged...).
       'mode' may be any of 'tcp_full', 'tcp_abridged'.

       Note that '.send()' and '.recv()' refer to messages, which
       will be packed accordingly, whereas '.write()' and '.read()'
       work on plain bytes, with no further additions.
    """

    def __init__(self, ip, port, mode='tcp_obfuscated',
                 proxy=None, timeout=timedelta(seconds=5)):
        self.ip = ip
        self.port = port
        self._mode = mode
        self.timeout = timeout

        self._send_counter = 0
        self._aes_encrypt, self._aes_decrypt = None, None

        # TODO Rename "TcpClient" as some sort of generic socket?
        self.conn = TcpClient(proxy=proxy)

        # Sending messages
        if mode == 'tcp_full':
            setattr(self, 'send', self._send_tcp_full)
            setattr(self, 'recv', self._recv_tcp_full)

        elif mode in ('tcp_abridged', 'tcp_obfuscated'):
            setattr(self, 'send', self._send_abridged)
            setattr(self, 'recv', self._recv_abridged)

        # Writing and reading from the socket
        if mode == 'tcp_obfuscated':
            setattr(self, 'write', self._write_obfuscated)
            setattr(self, 'read', self._read_obfuscated)
        else:
            setattr(self, 'write', self._write_plain)
            setattr(self, 'read', self._read_plain)

    def connect(self):
        self._send_counter = 0
        self.conn.connect(self.ip, self.port,
                          timeout=round(self.timeout.seconds))

        if self._mode == 'tcp_abridged':
            self.conn.write(int.to_bytes(239, 1, 'little'))
        elif self._mode == 'tcp_obfuscated':
            self._setup_obfuscation()

    def _setup_obfuscation(self):
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
        return self.conn.connected

    def close(self):
        self.conn.close()

    def cancel_receive(self):
        """Cancels (stops) trying to receive from the
        remote peer and raises a ReadCancelledError"""
        self.conn.cancel_read()

    def get_client_delay(self):
        """Gets the client read delay"""
        return self.conn.delay

    # region Receive message implementations

    def recv(self, **kwargs):
        """Receives and unpacks a message"""
        # TODO Don't ignore kwargs['timeout']?
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _recv_tcp_full(self, **kwargs):
        packet_length_bytes = self.read(4)
        packet_length = int.from_bytes(packet_length_bytes, 'little')

        seq_bytes = self.read(4)
        seq = int.from_bytes(seq_bytes, 'little')

        body = self.read(packet_length - 12)
        checksum = int.from_bytes(self.read(4), 'little')

        valid_checksum = crc32(packet_length_bytes + seq_bytes + body)
        if checksum != valid_checksum:
            raise InvalidChecksumError(checksum, valid_checksum)

        return body

    def _recv_abridged(self, **kwargs):
        length = int.from_bytes(self.read(1), 'little')
        if length >= 127:
            length = int.from_bytes(self.read(3) + b'\0', 'little')

        return self.read(length << 2)

    # endregion

    # region Send message implementations

    def send(self, message):
        """Encapsulates and sends the given message"""
        # Default implementation is just an error
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _send_tcp_full(self, message):
        # https://core.telegram.org/mtproto#tcp-transport
        # total length, sequence number, packet and checksum (CRC32)
        with BinaryWriter() as writer:
            writer.write_int(len(message) + 12)
            writer.write_int(self._send_counter)
            writer.write(message)
            writer.write_int(crc32(writer.get_bytes()), signed=False)
            self._send_counter += 1
            self.write(writer.get_bytes())

    def _send_abridged(self, message):
        with BinaryWriter() as writer:
            length = len(message) >> 2
            if length < 127:
                writer.write_byte(length)
            else:
                writer.write_byte(127)
                writer.write(int.to_bytes(length, 3, 'little'))
            writer.write(message)
            self.write(writer.get_bytes())

    # endregion

    # region Read implementations

    def read(self, length):
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _read_plain(self, length):
        return self.conn.read(length, timeout=self.timeout)

    def _read_obfuscated(self, length):
        return self._aes_decrypt.encrypt(
            self.conn.read(length, timeout=self.timeout)
        )

    # endregion

    # region Write implementations

    def write(self, data):
        raise ValueError('Invalid connection mode specified: ' + self._mode)

    def _write_plain(self, data):
        self.conn.write(data)

    def _write_obfuscated(self, data):
        self.conn.write(self._aes_encrypt.encrypt(data))

    # endregion
