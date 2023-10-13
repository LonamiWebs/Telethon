import os
from collections import namedtuple
from enum import IntEnum
from hashlib import sha1, sha256

from .aes import ige_decrypt, ige_encrypt
from .auth_key import AuthKey


# "where x = 0 for messages from client to server and x = 8 for those from server to client"
class Side(IntEnum):
    CLIENT = 0
    SERVER = 8


CalcKey = namedtuple("CalcKey", ("key", "iv"))


# https://core.telegram.org/mtproto/description#defining-aes-key-and-initialization-vector
def calc_key(auth_key: AuthKey, msg_key: bytes, side: Side) -> CalcKey:
    x = int(side)

    # sha256_a = SHA256 (msg_key + substr (auth_key, x, 36))
    sha256_a = sha256(msg_key + auth_key.data[x : x + 36]).digest()

    # sha256_b = SHA256 (substr (auth_key, 40+x, 36) + msg_key)
    sha256_b = sha256(auth_key.data[x + 40 : x + 76] + msg_key).digest()

    # aes_key = substr (sha256_a, 0, 8) + substr (sha256_b, 8, 16) + substr (sha256_a, 24, 8)
    aes_key = sha256_a[:8] + sha256_b[8:24] + sha256_a[24:32]

    # aes_iv = substr (sha256_b, 0, 8) + substr (sha256_a, 8, 16) + substr (sha256_b, 24, 8)
    aes_iv = sha256_b[:8] + sha256_a[8:24] + sha256_b[24:32]

    return CalcKey(aes_key, aes_iv)


def determine_padding_v2_length(length: int) -> int:
    return 16 + (16 - (length % 16))


def _do_encrypt_data_v2(
    plaintext: bytes, auth_key: AuthKey, random_padding: bytes
) -> bytes:
    padded_plaintext = (
        plaintext + random_padding[: determine_padding_v2_length(len(plaintext))]
    )

    side = Side.CLIENT
    x = int(side)

    # msg_key_large = SHA256 (substr (auth_key, 88+x, 32) + plaintext + random_padding)
    msg_key_large = sha256(auth_key.data[x + 88 : x + 120] + padded_plaintext).digest()

    # msg_key = substr (msg_key_large, 8, 16)
    msg_key = msg_key_large[8:24]

    key, iv = calc_key(auth_key, msg_key, side)
    ciphertext = ige_encrypt(padded_plaintext, key, iv)

    return auth_key.key_id + msg_key + ciphertext


def encrypt_data_v2(plaintext: bytes, auth_key: AuthKey) -> bytes:
    random_padding = os.urandom(32)
    return _do_encrypt_data_v2(plaintext, auth_key, random_padding)


def decrypt_data_v2(ciphertext: bytes, auth_key: AuthKey) -> bytes:
    side = Side.SERVER
    x = int(side)

    if len(ciphertext) < 24 or (len(ciphertext) - 24) % 16 != 0:
        raise ValueError("invalid ciphertext buffer length")

    # salt, session_id and sequence_number should also be checked.
    # However, not doing so has worked fine for years.

    key_id = ciphertext[:8]
    if auth_key.key_id != key_id:
        raise ValueError("server authkey mismatches with ours")

    msg_key = ciphertext[8:24]
    key, iv = calc_key(auth_key, msg_key, side)
    plaintext = ige_decrypt(ciphertext[24:], key, iv)

    # https://core.telegram.org/mtproto/security_guidelines#mtproto-encrypted-messages
    our_key = sha256(auth_key.data[x + 88 : x + 120] + plaintext).digest()
    if msg_key != our_key[8:24]:
        raise ValueError("server msgkey mismatches with ours")

    return plaintext


def generate_key_data_from_nonce(server_nonce: int, new_nonce: int) -> CalcKey:
    server_bytes = server_nonce.to_bytes(16)
    new_bytes = new_nonce.to_bytes(32)
    hash1 = sha1(new_bytes + server_bytes).digest()
    hash2 = sha1(server_bytes + new_bytes).digest()
    hash3 = sha1(new_bytes + new_bytes).digest()

    key = hash1 + hash2[:12]
    iv = hash2[12:20] + hash3 + new_bytes[:4]
    return CalcKey(key, iv)


def encrypt_ige(plaintext: bytes, key: bytes, iv: bytes) -> bytes:
    if len(plaintext) % 16 != 0:
        plaintext += os.urandom((16 - (len(plaintext) % 16)) % 16)
    return ige_encrypt(plaintext, key, iv)


def decrypt_ige(padded_ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    return ige_decrypt(padded_ciphertext, key, iv)
