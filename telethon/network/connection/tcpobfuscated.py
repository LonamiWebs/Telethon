import os

from .tcpabridged import AbridgedPacketCodec
from .connection import ObfuscatedConnection

from ...crypto import AESModeCTR


class ObfuscatedIO:
    header = None

    def __init__(self, connection):
        self._reader = connection._reader
        self._writer = connection._writer

        (self.header,
         self._encrypt,
         self._decrypt) = self.init_header(connection.packet_codec)

    @staticmethod
    def init_header(packet_codec):
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

        encryptor = AESModeCTR(encrypt_key, encrypt_iv)
        decryptor = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:60] = packet_codec.obfuscate_tag
        random[56:64] = encryptor.encrypt(bytes(random))[56:64]
        return (random, encryptor, decryptor)

    async def readexactly(self, n):
        return self._decrypt.encrypt(await self._reader.readexactly(n))

    def write(self, data):
        self._writer.write(self._encrypt.encrypt(data))


class ConnectionTcpObfuscated(ObfuscatedConnection):
    """
    Mode that Telegram defines as "obfuscated2". Encodes the packet
    just like `ConnectionTcpAbridged`, but encrypts every message with
    a randomly generated key using the AES-CTR mode so the packets are
    harder to discern.
    """
    obfuscated_io = ObfuscatedIO
    packet_codec = AbridgedPacketCodec
