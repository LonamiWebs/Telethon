import struct
from hashlib import sha1

from .. import helpers as utils
from ..extensions import BinaryReader


class AuthKey:
    def __init__(self, data):
        self.key = data

        with BinaryReader(sha1(self.key).digest()) as reader:
            self.aux_hash = reader.read_long(signed=False)
            reader.read(4)
            self.key_id = reader.read_long(signed=False)

    def calc_new_nonce_hash(self, new_nonce, number):
        """Calculates the new nonce hash based on
           the current class fields' values
        """
        new_nonce = new_nonce.to_bytes(32, 'little', signed=True)
        data = new_nonce + struct.pack('<BQ', number, self.aux_hash)
        return utils.calc_msg_key(data)
