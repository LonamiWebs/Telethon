import asyncio
import hashlib
import base64
import os

from .connection import ObfuscatedConnection
from .tcpabridged import AbridgedPacketCodec
from .tcpintermediate import (
    IntermediatePacketCodec,
    RandomizedIntermediatePacketCodec
)

from ...crypto import AESModeCTR


class MTProxyIO:
    """
    It's very similar to tcpobfuscated.ObfuscatedIO, but the way
    encryption keys, protocol tag and dc_id are encoded is different.
    """
    header = None

    def __init__(self, connection):
        self._reader = connection._reader
        self._writer = connection._writer

        (self.header,
         self._encrypt,
         self._decrypt) = self.init_header(
             connection._secret, connection._dc_id, connection.packet_codec)

    @staticmethod
    def init_header(secret, dc_id, packet_codec):
        # Validate
        is_dd = (len(secret) == 17) and (secret[0] == 0xDD)
        is_rand_codec = issubclass(
            packet_codec, RandomizedIntermediatePacketCodec)
        if is_dd and not is_rand_codec:
            raise ValueError(
                "Only RandomizedIntermediate can be used with dd-secrets")
        secret = secret[1:] if is_dd else secret
        if len(secret) != 16:
            raise ValueError(
                "MTProxy secret must be a hex-string representing 16 bytes")

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

        encryptor = AESModeCTR(encrypt_key, encrypt_iv)
        decryptor = AESModeCTR(decrypt_key, decrypt_iv)

        random[56:60] = packet_codec.obfuscate_tag

        dc_id_bytes = dc_id.to_bytes(2, "little", signed=True)
        random = random[:60] + dc_id_bytes + random[62:]
        random[56:64] = encryptor.encrypt(bytes(random))[56:64]
        return (random, encryptor, decryptor)

    async def readexactly(self, n):
        return self._decrypt.encrypt(await self._reader.readexactly(n))

    def write(self, data):
        self._writer.write(self._encrypt.encrypt(data))


class TcpMTProxy(ObfuscatedConnection):
    """
    Connector which allows user to connect to the Telegram via proxy servers
    commonly known as MTProxy.
    Implemented very ugly due to the leaky abstractions in Telethon networking
    classes that should be refactored later (TODO).

    .. warning::

        The support for TcpMTProxy classes is **EXPERIMENTAL** and prone to
        be changed. You shouldn't be using this class yet.
    """
    packet_codec = None
    obfuscated_io = MTProxyIO

    # noinspection PyUnusedLocal
    def __init__(self, ip, port, dc_id, *, loggers, proxy=None, local_addr=None):
        # connect to proxy's host and port instead of telegram's ones
        proxy_host, proxy_port = self.address_info(proxy)
        self._secret = self.normalize_secret(proxy[2])
        super().__init__(
            proxy_host, proxy_port, dc_id, loggers=loggers)

    async def _connect(self, timeout=None, ssl=None):
        await super()._connect(timeout=timeout, ssl=ssl)

        # Wait for EOF for 2 seconds (or if _wait_for_data's definition
        # is missing or different, just sleep for 2 seconds). This way
        # we give the proxy a chance to close the connection if the current
        # codec (which the proxy detects with the data we sent) cannot
        # be used for this proxy. This is a work around for #1134.
        # TODO Sleeping for N seconds may not be the best solution
        # TODO This fix could be welcome for HTTP proxies as well
        try:
            await asyncio.wait_for(self._reader._wait_for_data('proxy'), 2)
        except asyncio.TimeoutError:
            pass
        except Exception:
            await asyncio.sleep(2)

        if self._reader.at_eof():
            await self.disconnect()
            raise ConnectionError(
                'Proxy closed the connection after sending initial payload')

    @staticmethod
    def address_info(proxy_info):
        if proxy_info is None:
            raise ValueError("No proxy info specified for MTProxy connection")
        return proxy_info[:2]

    @staticmethod
    def normalize_secret(secret):
        if secret[:2] in ("ee", "dd"):  # Remove extra bytes
            secret = secret[2:]

        try:
            secret_bytes = bytes.fromhex(secret)
        except ValueError:
            secret = secret + '=' * (-len(secret) % 4)
            secret_bytes = base64.b64decode(secret.encode())

        return secret_bytes[:16]  # Remove the domain from the secret (until domain support is added)

class ConnectionTcpMTProxyAbridged(TcpMTProxy):
    """
    Connect to proxy using abridged protocol
    """
    packet_codec = AbridgedPacketCodec


class ConnectionTcpMTProxyIntermediate(TcpMTProxy):
    """
    Connect to proxy using intermediate protocol
    """
    packet_codec = IntermediatePacketCodec


class ConnectionTcpMTProxyRandomizedIntermediate(TcpMTProxy):
    """
    Connect to proxy using randomized intermediate protocol (dd-secrets)
    """
    packet_codec = RandomizedIntermediatePacketCodec
