"""Various helpers not related to the Telegram API itself"""
import os
import struct
from hashlib import sha1, sha256

from telethon.crypto import AES
from telethon.errors import SecurityError
from telethon.extensions import BinaryReader


# region Multiple utilities


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    return int.from_bytes(os.urandom(8), signed=signed, byteorder='little')


def ensure_parent_dir_exists(file_path):
    """Ensures that the parent directory exists"""
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

# endregion

# region Cryptographic related utils


def pack_message(session, message):
    """Packs a message following MtProto 2.0 guidelines"""
    # See https://core.telegram.org/mtproto/description
    data = struct.pack('<qq', session.salt, session.id) + bytes(message)
    padding = os.urandom(-(len(data) + 12) % 16 + 12)

    # Being substr(what, offset, length); x = 0 for client
    # "msg_key_large = SHA256(substr(auth_key, 88+x, 32) + pt + padding)"
    msg_key_large = sha256(
        session.auth_key.key[88:88 + 32] + data + padding).digest()

    # "msg_key = substr (msg_key_large, 8, 16)"
    msg_key = msg_key_large[8:24]
    aes_key, aes_iv = calc_key(session.auth_key.key, msg_key, True)

    key_id = struct.pack('<Q', session.auth_key.key_id)
    return key_id + msg_key + AES.encrypt_ige(data + padding, aes_key, aes_iv)


def unpack_message(session, reader):
    """Unpacks a message following MtProto 2.0 guidelines"""
    # See https://core.telegram.org/mtproto/description
    if reader.read_long(signed=False) != session.auth_key.key_id:
        raise SecurityError('Server replied with an invalid auth key')

    msg_key = reader.read(16)
    aes_key, aes_iv = calc_key(session.auth_key.key, msg_key, False)
    data = BinaryReader(AES.decrypt_ige(reader.read(), aes_key, aes_iv))

    data.read_long()  # remote_salt
    if data.read_long() != session.id:
        raise SecurityError('Server replied with a wrong session ID')

    remote_msg_id = data.read_long()
    remote_sequence = data.read_int()
    msg_len = data.read_int()
    message = data.read(msg_len)

    # https://core.telegram.org/mtproto/security_guidelines
    # Sections "checking sha256 hash" and "message length"
    if msg_key != sha256(
            session.auth_key.key[96:96 + 32] + data.get_bytes()).digest()[8:24]:
        raise SecurityError("Received msg_key doesn't match with expected one")

    return message, remote_msg_id, remote_sequence


def calc_key(auth_key, msg_key, client):
    """
    Calculate the key based on Telegram guidelines
    for MtProto 2, specifying whether it's the client or not.
    """
    # https://core.telegram.org/mtproto/description#defining-aes-key-and-initialization-vector
    x = 0 if client else 8

    sha256a = sha256(msg_key + auth_key[x: x + 36]).digest()
    sha256b = sha256(auth_key[x + 40:x + 76] + msg_key).digest()

    aes_key = sha256a[:8] + sha256b[8:24] + sha256a[24:32]
    aes_iv = sha256b[:8] + sha256a[8:24] + sha256b[24:32]

    return aes_key, aes_iv


def generate_key_data_from_nonce(server_nonce, new_nonce):
    """Generates the key data corresponding to the given nonce"""
    server_nonce = server_nonce.to_bytes(16, 'little', signed=True)
    new_nonce = new_nonce.to_bytes(32, 'little', signed=True)
    hash1 = sha1(new_nonce + server_nonce).digest()
    hash2 = sha1(server_nonce + new_nonce).digest()
    hash3 = sha1(new_nonce + new_nonce).digest()

    key = hash1 + hash2[:12]
    iv = hash2[12:20] + hash3 + new_nonce[:4]
    return key, iv


def get_password_hash(pw, current_salt):
    """Gets the password hash for the two-step verification.
       current_salt should be the byte array provided by
       invoking GetPasswordRequest()
    """

    # Passwords are encoded as UTF-8
    # At https://github.com/DrKLO/Telegram/blob/e31388
    # src/main/java/org/telegram/ui/LoginActivity.java#L2003
    data = pw.encode('utf-8')

    pw_hash = current_salt + data + current_salt
    return sha256(pw_hash).digest()

# endregion
