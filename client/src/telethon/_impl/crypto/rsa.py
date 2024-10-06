import struct
from hashlib import sha1, sha256

from rsa import PublicKey

from ..tl.core import serialize_bytes_to
from .aes import ige_encrypt


def compute_fingerprint(key: PublicKey) -> int:
    buffer = bytearray()
    serialize_bytes_to(buffer, key.n.to_bytes((key.n.bit_length() + 7) // 8))
    serialize_bytes_to(buffer, key.e.to_bytes((key.e.bit_length() + 7) // 8))
    fingerprint = struct.unpack("<q", sha1(buffer).digest()[-8:])[0]
    assert isinstance(fingerprint, int)
    return fingerprint


def encrypt_hashed(data: bytes, key: PublicKey, random_bytes: bytes) -> bytes:
    # https://core.telegram.org/mtproto/auth_key#41-rsa-paddata-server-public-key-mentioned-above-is-implemented-as-follows

    # data_with_padding := data + random_padding_bytes; -- where random_padding_bytes are chosen so that the resulting length of data_with_padding is precisely 192 bytes, and data is the TL-serialized data to be encrypted as before. One has to check that data is not longer than 144 bytes.
    if len(data) > 144:
        raise ValueError("data must be 144 bytes at most")

    data_with_padding = data + random_bytes[: 192 - len(data)]

    # data_pad_reversed := BYTE_REVERSE(data_with_padding); -- is obtained from data_with_padding by reversing the byte order.
    data_pad_reversed = data_with_padding[::-1]

    attempt = 0
    while 192 + 32 * attempt + 32 <= len(random_bytes):
        # a random 32-byte temp_key is generated.
        temp_key = random_bytes[192 + 32 * attempt : 192 + 32 * attempt + 32]

        # data_with_hash := data_pad_reversed + SHA256(temp_key + data_with_padding); -- after this assignment, data_with_hash is exactly 224 bytes long.
        data_with_hash = (
            data_pad_reversed + sha256(temp_key + data_with_padding).digest()
        )

        # aes_encrypted := AES256_IGE(data_with_hash, temp_key, 0); -- AES256-IGE encryption with zero IV.
        aes_encrypted = ige_encrypt(data_with_hash, temp_key, bytes(32))

        # temp_key_xor := temp_key XOR SHA256(aes_encrypted); -- adjusted key, 32 bytes
        temp_key_xor = bytes(
            a ^ b for a, b in zip(temp_key, sha256(aes_encrypted).digest())
        )

        # key_aes_encrypted := temp_key_xor + aes_encrypted; -- exactly 256 bytes (2048 bits) long
        key_aes_encrypted = temp_key_xor + aes_encrypted

        # The value of key_aes_encrypted is compared with the RSA-modulus of server_pubkey as a big-endian 2048-bit (256-byte) unsigned integer. If key_aes_encrypted turns out to be greater than or equal to the RSA modulus, the previous steps starting from the generation of new random temp_key are repeated. Otherwise the final step is performed:
        if int.from_bytes(key_aes_encrypted) < key.n:
            break

        attempt += 1
    else:
        raise RuntimeError("ran out of entropy")

    # encrypted_data := RSA(key_aes_encrypted, server_pubkey); -- 256-byte big-endian integer is elevated to the requisite power from the RSA public key modulo the RSA modulus, and the result is stored as a big-endian integer consisting of exactly 256 bytes (with leading zero bytes if required).
    payload = int.from_bytes(key_aes_encrypted)
    encrypted = pow(payload, key.e, key.n)
    return encrypted.to_bytes(256)


# From my.telegram.org.
PRODUCTION_RSA_KEY = PublicKey.load_pkcs1(
    b"""-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEA6LszBcC1LGzyr992NzE0ieY+BSaOW622Aa9Bd4ZHLl+TuFQ4lo4g
5nKaMBwK/BIb9xUfg0Q29/2mgIR6Zr9krM7HjuIcCzFvDtr+L0GQjae9H0pRB2OO
62cECs5HKhT5DZ98K33vmWiLowc621dQuwKWSQKjWf50XYFw42h21P2KXUGyp2y/
+aEyZ+uVgLLQbRA1dEjSDZ2iGRy12Mk5gpYc397aYp438fsJoHIgJ2lgMv5h7WY9
t6N/byY9Nw9p21Og3AoXSL2q/2IJ1WRUhebgAdGVMlV1fkuOQoEzR7EdpqtQD9Cs
5+bfo3Nhmcyvk5ftB0WkJ9z6bNZ7yxrP8wIDAQAB
-----END RSA PUBLIC KEY-----"""
)

TESTMODE_RSA_KEY = PublicKey.load_pkcs1(
    b"""-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAyMEdY1aR+sCR3ZSJrtztKTKqigvO/vBfqACJLZtS7QMgCGXJ6XIR
yy7mx66W0/sOFa7/1mAZtEoIokDP3ShoqF4fVNb6XeqgQfaUHd8wJpDWHcR2OFwv
plUUI1PLTktZ9uW2WE23b+ixNwJjJGwBDJPQEQFBE+vfmH0JP503wr5INS1poWg/
j25sIWeYPHYeOrFp/eXaqhISP6G+q2IeTaWTXpwZj4LzXq5YOpk4bYEQ6mvRq7D1
aHWfYmlEGepfaYR8Q0YqvvhYtMte3ITnuSJs171+GDqpdKcSwHnd6FudwGO4pcCO
j4WcDuXc2CTHgH8gFTNhp/Y8/SpDOhvn9QIDAQAB
-----END RSA PUBLIC KEY-----"""
)


RSA_KEYS = {
    compute_fingerprint(key): key for key in (PRODUCTION_RSA_KEY, TESTMODE_RSA_KEY)
}
