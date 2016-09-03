import os
from utils.binary_writer import BinaryWriter
import hashlib


bits_per_byte = 8


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    return int.from_bytes(os.urandom(8), signed=signed, byteorder='little')


def generate_random_bytes(count):
    """Generates a random bytes array"""
    return os.urandom(count)


def get_byte_array(integer, signed):
    bits = integer.bit_length()
    byte_length = (bits + bits_per_byte - 1) // bits_per_byte
    # For some strange reason, this has to be big!
    return int.to_bytes(integer, length=byte_length, byteorder='big', signed=signed)


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


def calc_msg_key_offset(data, offset, limit):
    """Calculates the message key from offset given data, with an optional offset and limit"""
    return sha1(data[offset:offset + limit])[4:20]


def generate_key_data_from_nonces(server_nonce, new_nonce):
    hash1 = sha1(bytes(new_nonce + server_nonce))
    hash2 = sha1(bytes(server_nonce + new_nonce))
    hash3 = sha1(bytes(new_nonce + new_nonce))

    with BinaryWriter() as key_buffer:
        with BinaryWriter() as iv_buffer:
            key_buffer.write(hash1)
            key_buffer.write(hash2[:12])

            iv_buffer.write(hash2[12:20])
            iv_buffer.write(hash3)
            iv_buffer.write_byte(new_nonce[:4])

            return key_buffer.get_bytes(), iv_buffer.get_bytes()


def sha1(data):
    sha = hashlib.sha1()
    sha.update(data)
    return sha.digest()
