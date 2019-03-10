import hashlib
import os

from .connection import Connection
from .tcpabridged import AbridgedPacket
from .tcpintermediate import IntermediatePacket, RandomizedIntermediatePacket

from ...crypto import AESModeCTR


class TcpMTProxy(Connection):
    """
    Connector which allows user to connect to the Telegram via proxy servers
    commonly known as MTProxy.
    Implemented very ugly due to the leaky abstractions in Telethon networking
    classes that should be refactored later (TODO).

    .. warning::

        The support for MTProtoProxies class is **EXPERIMENTAL** and prone to
        be changed. You shouldn't be using this class yet.
    """
    packet_codec = None

    @staticmethod
    def address_info(proxy_info):
        if proxy_info is None:
            raise ValueError("No proxy info specified for MTProxy connection")
        return proxy_info[:2]

    def __init__(self, ip, port, dc_id, *, loop, loggers, proxy=None):
        proxy_host, proxy_port = self.address_info(proxy)
        super().__init__(
            proxy_host, proxy_port, dc_id, loop=loop, loggers=loggers)
        self._codec = self.packet_codec()
        secret = bytes.fromhex(proxy[2])
        is_dd = (len(secret) == 17) and (secret[0] == 0xDD)
        if is_dd and (self.packet_codec != RandomizedIntermediatePacket):
            raise ValueError(
                "Only RandomizedIntermediate can be used with dd-secrets")
        secret = secret[:-1] if is_dd else secret
        if len(secret) != 16:
            raise ValueError(
                "MTProxy secret must be a hex-string representing 16 bytes")
        self._dc_id = dc_id
        self._secret = secret

    def _init_conn(self):
        self._obfuscation = MTProxyIO(self._reader, self._writer,
                                      self._codec.mtproto_proxy_tag,
                                      self._secret, self._dc_id)
        self._writer.write(self._obfuscation.header)

    def _send(self, data):
        self._obfuscation.write(self._codec.encode_packet(data))

    async def _recv(self):
        return await self._codec.read_packet(self._obfuscation)


class ConnectionTcpMTProxyAbridged(TcpMTProxy):
    """
    Connect to proxy using abridged protocol
    """
    packet_codec = AbridgedPacket


class ConnectionTcpMTProxyIntermediate(TcpMTProxy):
    """
    Connect to proxy using intermediate protocol
    """
    packet_codec = IntermediatePacket


class ConnectionTcpMTProxyRandomizedIntermediate(TcpMTProxy):
    """
    Connect to proxy using randomized intermediate protocol (dd-secrets)
    """
    packet_codec = RandomizedIntermediatePacket


class MTProxyIO:
    """
    It's very similar to tcpobfuscated.ObfuscatedIO, but the way
    encryption keys, protocol tag and dc_id are encoded is different.
    """
    header = None

    def __init__(self, reader, writer, protocol_tag, secret, dc_id):
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
        encrypt_key = hashlib.sha256(
            bytes(random[8:40]) + secret).digest()
        encrypt_iv = bytes(random[40:56])
        decrypt_key = hashlib.sha256(
            bytes(random_reversed[:32]) + secret).digest()
        decrypt_iv = bytes(random_reversed[32:48])

        self._aes_encrypt = AESModeCTR(encrypt_key, encrypt_iv)
        self._aes_decrypt = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:60] = protocol_tag

        dc_id_bytes = dc_id.to_bytes(2, "little", signed=True)
        random = random[:60] + dc_id_bytes + random[62:]
        random[56:64] = self._aes_encrypt.encrypt(bytes(random))[56:64]

        self.header = random

    async def readexactly(self, n):
        return self._aes_decrypt.encrypt(await self._reader.readexactly(n))

    def write(self, data):
        self._writer.write(self._aes_encrypt.encrypt(data))
