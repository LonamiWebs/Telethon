"""Various helpers not related to the Telegram API itself"""
from hashlib import sha1, sha256
import os

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


def calc_key(shared_key, msg_key, client):
    """Calculate the key based on Telegram guidelines, specifying whether it's the client or not"""
    x = 0 if client else 8

    sha1a = sha1(msg_key + shared_key[x:x + 32]).digest()
    sha1b = sha1(shared_key[x + 32:x + 48] + msg_key +
                 shared_key[x + 48:x + 64]).digest()

    sha1c = sha1(shared_key[x + 64:x + 96] + msg_key).digest()
    sha1d = sha1(msg_key + shared_key[x + 96:x + 128]).digest()

    key = sha1a[0:8] + sha1b[8:20] + sha1c[4:16]
    iv = sha1a[8:20] + sha1b[0:8] + sha1c[16:20] + sha1d[0:8]

    return key, iv


def calc_msg_key(data):
    """Calculates the message key from the given data"""
    return sha1(data).digest()[4:20]


def generate_key_data_from_nonce(server_nonce, new_nonce):
    """Generates the key data corresponding to the given nonce"""
    hash1 = sha1(bytes(new_nonce + server_nonce)).digest()
    hash2 = sha1(bytes(server_nonce + new_nonce)).digest()
    hash3 = sha1(bytes(new_nonce + new_nonce)).digest()

    key = hash1 + hash2[:12]
    iv = hash2[12:20] + hash3 + new_nonce[:4]
    return key, iv


def get_password_hash(pw, current_salt):
    """Gets the password hash for the two-step verification.
       current_salt should be the byte array provided by invoking GetPasswordRequest()"""

    # Passwords are encoded as UTF-8
    # At https://github.com/DrKLO/Telegram/blob/e31388
    # src/main/java/org/telegram/ui/LoginActivity.java#L2003
    data = pw.encode('utf-8')

    pw_hash = current_salt + data + current_salt
    return sha256(pw_hash).digest()

# endregion
