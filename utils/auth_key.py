# This file is based on TLSharp
# https://github.com/sochix/TLSharp/blob/master/TLSharp.Core/MTProto/Crypto/AuthKey.cs
from hashlib import sha1
from utils.binary_writer import BinaryWriter
from utils.binary_reader import BinaryReader


class AuthKey:
    def __init__(self, gab=None, data=None):
        if gab:
            self.key = gab.to_byte_array_unsigned()
        elif data:
            self.key = data
        else:
            raise AssertionError('Either a gab integer or data bytes array must be provided')

        with BinaryReader(sha1(self.key)) as reader:
            self.aux_hash = reader.read_long(signed=False)
            reader.read(4)
            self.key_id = reader.read_long(signed=False)


    def calc_new_nonce_hash(self, new_nonce, number):
        with BinaryWriter() as writer:
            writer.write(new_nonce)
            writer.write_byte(number)
            writer.write_long(self.aux_hash, signed=False)

            new_nonce_hash = sha1(writer.get_bytes())[4:20]
            return new_nonce_hash
