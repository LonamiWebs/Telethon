import pyaes


def ige_encrypt(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    assert len(plaintext) % 16 == 0
    assert len(iv) == 32

    aes = pyaes.AES(key)
    iv1 = iv[:16]
    iv2 = iv[16:]

    ciphertext = bytearray()

    for block_offset in range(0, len(plaintext), 16):
        plaintext_block = plaintext[block_offset : block_offset + 16]
        ciphertext_block = bytes(
            a ^ b
            for a, b in zip(
                aes.encrypt([a ^ b for a, b in zip(plaintext_block, iv1)]), iv2
            )
        )
        iv1 = ciphertext_block
        iv2 = plaintext_block

        ciphertext += ciphertext_block

    return bytes(ciphertext)


def ige_decrypt(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    assert len(ciphertext) % 16 == 0
    assert len(iv) == 32

    aes = pyaes.AES(key)
    iv1 = iv[:16]
    iv2 = iv[16:]

    plaintext = bytearray()

    for block_offset in range(0, len(ciphertext), 16):
        ciphertext_block = ciphertext[block_offset : block_offset + 16]
        plaintext_block = bytes(
            a ^ b
            for a, b in zip(
                aes.decrypt([a ^ b for a, b in zip(ciphertext_block, iv2)]), iv1
            )
        )
        iv1 = ciphertext_block
        iv2 = plaintext_block

        plaintext += plaintext_block

    return bytes(plaintext)
