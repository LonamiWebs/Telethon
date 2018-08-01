"""
AES IGE implementation in Python.

If available, cryptg will be used instead, otherwise
if available, libssl will be used instead, otherwise
the Python implementation will be used.
"""
import os
import pyaes
import logging
from . import libssl


__log__ = logging.getLogger(__name__)


try:
    import cryptg
    __log__.info('cryptg detected, it will be used for encryption')
except ImportError:
    cryptg = None
    if libssl.encrypt_ige and libssl.decrypt_ige:
        __log__.info('libssl detected, it will be used for encryption')
    else:
        __log__.info('cryptg module not installed and libssl not found, '
                     'falling back to (slower) Python encryption')


class AES:
    """
    Class that servers as an interface to encrypt and decrypt
    text through the AES IGE mode.
    """
    @staticmethod
    def decrypt_ige(cipher_text, key, iv):
        """
        Decrypts the given text in 16-bytes blocks by using the
        given key and 32-bytes initialization vector.
        """
        if cryptg:
            return cryptg.decrypt_ige(cipher_text, key, iv)
        if libssl.decrypt_ige:
            return libssl.decrypt_ige(cipher_text, key, iv)

        iv1 = iv[:len(iv) // 2]
        iv2 = iv[len(iv) // 2:]

        aes = pyaes.AES(key)

        plain_text = []
        blocks_count = len(cipher_text) // 16

        cipher_text_block = [0] * 16
        for block_index in range(blocks_count):
            for i in range(16):
                cipher_text_block[i] = \
                    cipher_text[block_index * 16 + i] ^ iv2[i]

            plain_text_block = aes.decrypt(cipher_text_block)

            for i in range(16):
                plain_text_block[i] ^= iv1[i]

            iv1 = cipher_text[block_index * 16:block_index * 16 + 16]
            iv2 = plain_text_block

            plain_text.extend(plain_text_block)

        return bytes(plain_text)

    @staticmethod
    def encrypt_ige(plain_text, key, iv):
        """
        Encrypts the given text in 16-bytes blocks by using the
        given key and 32-bytes initialization vector.
        """
        padding = len(plain_text) % 16
        if padding:
            plain_text += os.urandom(16 - padding)

        if cryptg:
            return cryptg.encrypt_ige(plain_text, key, iv)
        if libssl.encrypt_ige:
            return libssl.encrypt_ige(plain_text, key, iv)

        iv1 = iv[:len(iv) // 2]
        iv2 = iv[len(iv) // 2:]

        aes = pyaes.AES(key)

        cipher_text = []
        blocks_count = len(plain_text) // 16

        for block_index in range(blocks_count):
            plain_text_block = list(
                plain_text[block_index * 16:block_index * 16 + 16]
            )
            for i in range(16):
                plain_text_block[i] ^= iv1[i]

            cipher_text_block = aes.encrypt(plain_text_block)

            for i in range(16):
                cipher_text_block[i] ^= iv2[i]

            iv1 = cipher_text_block
            iv2 = plain_text[block_index * 16:block_index * 16 + 16]

            cipher_text.extend(cipher_text_block)

        return bytes(cipher_text)
