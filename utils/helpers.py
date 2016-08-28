import random
from utils.binary_writer import BinaryWriter
from hashlib import sha1


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    result = random.getrandbits(64)
    if not signed:
        result &= 0xFFFFFFFFFFFFFFFF  # Ensure it's unsigned

    return result


def generate_random_bytes(count):
    """Generates a random bytes array"""
    with BinaryWriter() as writer:
        for _ in range(count):
            writer.write(random.getrandbits(8))

    return writer.get_bytes()


def calc_key(shared_key, msg_key, client):
    """Calculate the key based on Telegram guidelines, specifying whether it's the client or not"""
    x = 0 if client else 8

    buffer = [0] * 48
    buffer[0:16] = msg_key
    buffer[16:48] = shared_key[x:x + 32]
    sha1a = sha1(buffer)

    buffer[0:16] = shared_key[x + 32:x + 48]
    buffer[16:32] = msg_key
    buffer[32:48] = shared_key[x + 48:x + 64]
    sha1b = sha1(buffer)

    buffer[0:32] = shared_key[x + 64:x + 96]
    buffer[32:48] = msg_key
    sha1c = sha1(buffer)

    buffer[0:16] = msg_key
    buffer[16:48] = shared_key[x + 96:x + 128]
    sha1d = sha1(buffer)

    key = sha1a[0:8] + sha1b[8:20] + sha1c[4:16]
    iv = sha1a[8:20] + sha1b[0:8] + sha1c[16:20] + sha1d[0:8]

    return key, iv


def calc_msg_key(data):
    """Calculates the message key from the given data"""
    return sha1(data)[4:20]


def calc_msg_key_offset(data, offset, limit):
    """Calculates the message key from offset given data, with an optional offset and limit"""
    # TODO untested, may not be offset like this
    # In the original code it was as parameters for the sha function, not slicing the array
    return sha1(data[offset:offset + limit])[4:20]
