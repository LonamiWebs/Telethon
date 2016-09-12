import os
import shutil
from utils import BinaryWriter
import hashlib

# region Multiple utilities


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    return int.from_bytes(os.urandom(8), signed=signed, byteorder='little')


def generate_random_bytes(count):
    """Generates a random bytes array"""
    return os.urandom(count)


def load_settings(path='api/settings'):
    """Loads the user settings located under `api/`"""
    settings = {}
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            value_pair = line.split('=')
            left = value_pair[0].strip()
            right = value_pair[1].strip()
            if right.isnumeric():
                settings[left] = int(right)
            else:
                settings[left] = right

    return settings


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

    sha1a = sha1(msg_key + shared_key[x:x + 32])
    sha1b = sha1(shared_key[x + 32:x + 48] + msg_key + shared_key[x + 48:x + 64])
    sha1c = sha1(shared_key[x + 64:x + 96] + msg_key)
    sha1d = sha1(msg_key + shared_key[x + 96:x + 128])

    key = sha1a[0:8] + sha1b[8:20] + sha1c[4:16]
    iv = sha1a[8:20] + sha1b[0:8] + sha1c[16:20] + sha1d[0:8]

    return key, iv


def calc_msg_key(data):
    """Calculates the message key from the given data"""
    return sha1(data)[4:20]


def generate_key_data_from_nonces(server_nonce, new_nonce):
    """Generates the key data corresponding to the given nonces"""
    hash1 = sha1(bytes(new_nonce + server_nonce))
    hash2 = sha1(bytes(server_nonce + new_nonce))
    hash3 = sha1(bytes(new_nonce + new_nonce))

    with BinaryWriter() as key_buffer:
        with BinaryWriter() as iv_buffer:
            key_buffer.write(hash1)
            key_buffer.write(hash2[:12])

            iv_buffer.write(hash2[12:20])
            iv_buffer.write(hash3)
            iv_buffer.write(new_nonce[:4])

            return key_buffer.get_bytes(), iv_buffer.get_bytes()


def sha1(data):
    """Calculates the SHA1 digest for the given data"""
    sha = hashlib.sha1()
    sha.update(data)
    return sha.digest()

# endregion
