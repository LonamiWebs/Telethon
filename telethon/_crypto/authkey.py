"""
This module holds the AuthKey class.
"""
import struct
from hashlib import sha1

from ..extensions import BinaryReader


class AuthKey:
    """
    Represents an authorization key, used to encrypt and decrypt
    messages sent to Telegram's data centers.
    """
    def __init__(self, data):
        """
        Initializes a new authorization key.

        :param data: the data in bytes that represent this auth key.
        """
        self.key = data

    @property
    def key(self):
        return self._key

    @key.setter
    def key(self, value):
        if not value:
            self._key = self.aux_hash = self.key_id = None
            return

        if isinstance(value, type(self)):
            self._key, self.aux_hash, self.key_id = \
                value._key, value.aux_hash, value.key_id
            return

        self._key = value
        with BinaryReader(sha1(self._key).digest()) as reader:
            self.aux_hash = reader.read_long(signed=False)
            reader.read(4)
            self.key_id = reader.read_long(signed=False)

    # TODO This doesn't really fit here, it's only used in authentication
    def calc_new_nonce_hash(self, new_nonce, number):
        """
        Calculates the new nonce hash based on the current attributes.

        :param new_nonce: the new nonce to be hashed.
        :param number: number to prepend before the hash.
        :return: the hash for the given new nonce.
        """
        new_nonce = new_nonce.to_bytes(32, 'little', signed=True)
        data = new_nonce + struct.pack('<BQ', number, self.aux_hash)

        # Calculates the message key from the given data
        return int.from_bytes(sha1(data).digest()[4:20], 'little', signed=True)

    def __bool__(self):
        return bool(self._key)

    def __eq__(self, other):
        return isinstance(other, type(self)) and other.key == self._key
