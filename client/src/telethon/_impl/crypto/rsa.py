import os
import struct
from hashlib import sha1

from rsa import PublicKey, encrypt

from ..tl.core import serialize_bytes_to


def compute_fingerprint(key: PublicKey) -> int:
    buffer = bytearray()
    serialize_bytes_to(buffer, key.n.to_bytes((key.n.bit_length() + 7) // 8))
    serialize_bytes_to(buffer, key.e.to_bytes((key.e.bit_length() + 7) // 8))
    fingerprint = struct.unpack("<q", sha1(buffer).digest()[-8:])[0]
    assert isinstance(fingerprint, int)
    return fingerprint


def encrypt_hashed(data: bytes, key: PublicKey, random_data: bytes) -> bytes:
    # Cannot use `rsa.encrypt` because it's not deterministic and requires its own padding.
    padding_length = 235 - len(data)
    assert padding_length >= 0 and len(random_data) >= padding_length
    to_encrypt = sha1(data).digest() + data + random_data[:padding_length]
    payload = int.from_bytes(to_encrypt)
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
