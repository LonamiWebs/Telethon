"""
AES IGE implementation in Python. This module may use libssl if available.
"""
import os
import pyaes

try:
    import cryptg
except ImportError:
    cryptg = None


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
        # Add random padding iff it's not evenly divisible by 16 already
        if len(plain_text) % 16 != 0:
            padding_count = 16 - len(plain_text) % 16
            plain_text += os.urandom(padding_count)

        if cryptg:
            return cryptg.encrypt_ige(plain_text, key, iv)

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
