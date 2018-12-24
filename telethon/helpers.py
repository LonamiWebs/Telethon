"""Various helpers not related to the Telegram API itself"""
import os
import struct
from hashlib import sha1, sha256


# region Multiple utilities


def generate_random_long(signed=True):
    """Generates a random long integer (8 bytes), which is optionally signed"""
    return int.from_bytes(os.urandom(8), signed=signed, byteorder='little')


def ensure_parent_dir_exists(file_path):
    """Ensures that the parent directory exists"""
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def add_surrogate(text):
    return ''.join(
        # SMP -> Surrogate Pairs (Telegram offsets are calculated with these).
        # See https://en.wikipedia.org/wiki/Plane_(Unicode)#Overview for more.
        ''.join(chr(y) for y in struct.unpack('<HH', x.encode('utf-16le')))
        if (0x10000 <= ord(x) <= 0x10FFFF) else x for x in text
    )


def del_surrogate(text):
    return text.encode('utf-16', 'surrogatepass').decode('utf-16')


def strip_text(text, entities):
    """
    Strips whitespace from the given text modifying the provided entities.

    This assumes that there are no overlapping entities, that their length
    is greater or equal to one, and that their length is not out of bounds.
    """
    if not entities:
        return text.strip()

    while text and text[-1].isspace():
        e = entities[-1]
        if e.offset + e.length == len(text):
            if e.length == 1:
                del entities[-1]
                if not entities:
                    return text.strip()
            else:
                e.length -= 1
        text = text[:-1]

    while text and text[0].isspace():
        for i in reversed(range(len(entities))):
            e = entities[i]
            if e.offset != 0:
                e.offset -= 1
                continue

            if e.length == 1:
                del entities[0]
                if not entities:
                    return text.lstrip()
            else:
                e.length -= 1

        text = text[1:]

    return text


# endregion

# region Cryptographic related utils


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


# endregion

# region Custom Classes


class TotalList(list):
    """
    A list with an extra `total` property, which may not match its `len`
    since the total represents the total amount of items *available*
    somewhere else, not the items *in this list*.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total = 0

    def __str__(self):
        return '[{}, total={}]'.format(
            ', '.join(str(x) for x in self), self.total)

    def __repr__(self):
        return '[{}, total={}]'.format(
            ', '.join(repr(x) for x in self), self.total)


# endregion
