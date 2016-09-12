import pyaes


class AES:
    @staticmethod
    def decrypt_ige(cipher_text, key, iv):
        """Decrypts the given text in 16-bytes blocks by using the given key and 32-bytes initialization vector"""
        iv1 = iv[:len(iv)//2]
        iv2 = iv[len(iv)//2:]

        aes = pyaes.AES(key)

        plain_text = [0] * len(cipher_text)
        blocks_count = len(cipher_text) // 16

        cipher_text_block = [0] * 16
        for block_index in range(blocks_count):
            for i in range(16):
                cipher_text_block[i] = cipher_text[block_index * 16 + i] ^ iv2[i]

            plain_text_block = aes.decrypt(cipher_text_block)

            for i in range(16):
                plain_text_block[i] ^= iv1[i]

            iv1 = cipher_text[block_index * 16:block_index * 16 + 16]
            iv2 = plain_text_block[0:16]

            plain_text[block_index * 16:block_index * 16 + 16] = plain_text_block[:16]

        return bytes(plain_text)

    @staticmethod
    def encrypt_ige(plain_text, key, iv):
        """Encrypts the given text in 16-bytes blocks by using the given key and 32-bytes initialization vector"""
        # TODO: Random padding?
        if len(plain_text) % 16 != 0:  # Add padding if and only if it's not evenly divisible by 16 already
            padding = bytes(16 - len(plain_text) % 16)
            plain_text += padding

        iv1 = iv[:len(iv)//2]
        iv2 = iv[len(iv)//2:]

        aes = pyaes.AES(key)

        blocks_count = len(plain_text) // 16
        cipher_text = [0] * len(plain_text)

        for block_index in range(blocks_count):
            plain_text_block = list(plain_text[block_index * 16:block_index * 16 + 16])
            for i in range(16):
                plain_text_block[i] ^= iv1[i]

            cipher_text_block = aes.encrypt(plain_text_block)

            for i in range(16):
                cipher_text_block[i] ^= iv2[i]

            iv1 = cipher_text_block[0:16]
            iv2 = plain_text[block_index * 16:block_index * 16 + 16]

            cipher_text[block_index * 16:block_index * 16 + 16] = cipher_text_block[:16]

        return bytes(cipher_text)
