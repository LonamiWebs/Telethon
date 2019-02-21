import os

from .connection import Connection
from .tcpabridged import ConnectionTcpAbridged
from ...crypto import AESModeCTR


class ConnectionTcpObfuscated(ConnectionTcpAbridged):
    """
    Mode that Telegram defines as "obfuscated2". Encodes the packet
    just like `ConnectionTcpAbridged`, but encrypts every message with
    a randomly generated key using the AES-CTR mode so the packets are
    harder to discern.
    """
    def __init__(self, ip, port, dc_id, *, loop, loggers, proxy=None):
        super().__init__(
            ip, port, dc_id, loop=loop, loggers=loggers, proxy=proxy)
        self._aes_encrypt = None
        self._aes_decrypt = None

    def _write(self, data):
        self._writer.write(self._aes_encrypt.encrypt(data))

    async def _read(self, n):
        return self._aes_decrypt.encrypt(await self._reader.readexactly(n))

    def _init_conn(self):
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
        encrypt_key = self._compose_key(bytes(random[8:40]))
        encrypt_iv = bytes(random[40:56])
        decrypt_key = self._compose_key(bytes(random_reversed[:32]))
        decrypt_iv = bytes(random_reversed[32:48])

        self._aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
        self._aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:60] = b'\xef\xef\xef\xef'
        random[56:64] = self._compose_tail(bytes(random))

        self._writer.write(random)

    # Next functions provide the variable parts of the connection handshake.
    # This is necessary to modify obfuscated2 the way that MTProxy requires.
    def _compose_key(self, data):
        return data

    def _compose_tail(self, data):
        return self._aes_encrypt.encrypt(data)[56:64]
