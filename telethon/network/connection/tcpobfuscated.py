import os

from .tcpabridged import AbridgedPacket
from .connection import Connection

from ...crypto import AESModeCTR


class ConnectionTcpObfuscated(Connection):
    """
    Mode that Telegram defines as "obfuscated2". Encodes the packet
    just like `ConnectionTcpAbridged`, but encrypts every message with
    a randomly generated key using the AES-CTR mode so the packets are
    harder to discern.
    """
    def __init__(self, ip, port, dc_id, *, loop, loggers, proxy=None):
        super().__init__(
            ip, port, dc_id, loop=loop, loggers=loggers, proxy=proxy)
        self._codec = AbridgedPacket()

    def _init_conn(self):
        self._obfuscation = ObfuscatedIO(
            self._reader, self._writer, self._codec.mtproto_proxy_tag)
        self._writer.write(self._obfuscation.header)

    def _send(self, data):
        self._obfuscation.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._obfuscation)


class ObfuscatedIO:
    header = None

    def __init__(self, reader, writer, protocol_tag):
        self._reader = reader
        self._writer = writer
        # Obfuscated messages secrets cannot start with any of these
        keywords = (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')
        while True:
            random = os.urandom(64)
            if (random[0] != 0xef and
                    random[:4] not in keywords and
                    random[4:4] != b'\0\0\0\0'):
                break

        random = bytearray(random)
        random_reversed = random[55:7:-1]  # Reversed (8, len=48)

        # Encryption has "continuous buffer" enabled
        encrypt_key = bytes(random[8:40])
        encrypt_iv = bytes(random[40:56])
        decrypt_key = bytes(random_reversed[:32])
        decrypt_iv = bytes(random_reversed[32:48])

        self._aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
        self._aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:60] = protocol_tag
        random[56:64] = self._aes_encrypt.encrypt(bytes(random))[56:64]

        self.header = random

    async def readexactly(self, n):
        return self._aes_decrypt.encrypt(await self._reader.readexactly(n))

    def write(self, data):
        self._writer.write(self._aes_encrypt.encrypt(data))
