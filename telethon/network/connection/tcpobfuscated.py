import os

from .tcpabridged import ConnectionTcpAbridged
from ...crypto import AESModeCTR


class ConnectionTcpObfuscated(ConnectionTcpAbridged):
    """
    Encodes the packet just like `ConnectionTcpAbridged`, but encrypts
    every message with a randomly generated key using the
    AES-CTR mode so the packets are harder to discern.
    """
    def __init__(self, ip, port, *, loop, loggers, proxy=None):
        super().__init__(ip, port, loop=loop, loggers=loggers, proxy=proxy)
        self._aes_encrypt = None
        self._aes_decrypt = None

    def _write(self, data):
        self._writer.write(self._aes_encrypt.encrypt(data))

    async def _read(self, n):
        return self._aes_decrypt.encrypt(await self._reader.readexactly(n))

    async def connect(self, timeout=None, ssl=None):
        await super().connect(timeout=timeout, ssl=ssl)

        # Obfuscated messages secrets cannot start with any of these
        keywords = (b'PVrG', b'GET ', b'POST', b'\xee\xee\xee\xee')
        while True:
            random = os.urandom(64)
            if (random[0] != b'\xef' and
                    random[:4] not in keywords and
                    random[4:4] != b'\0\0\0\0'):
                break

        random = bytearray(random)
        random[56] = random[57] = random[58] = random[59] = 0xef
        random_reversed = random[55:7:-1]  # Reversed (8, len=48)

        # Encryption has "continuous buffer" enabled
        encrypt_key = bytes(random[8:40])
        encrypt_iv = bytes(random[40:56])
        decrypt_key = bytes(random_reversed[:32])
        decrypt_iv = bytes(random_reversed[32:48])

        self._aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
        self._aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:64] = self._aes_encrypt.encrypt(bytes(random))[56:64]
        self._writer.write(random)
        await self._writer.drain()
