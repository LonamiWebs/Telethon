import os
from hashlib import sha1

from ..extensions import BinaryWriter


class RSAServerKey:
    def __init__(self, fingerprint, m, e):
        self.fingerprint = fingerprint
        self.m = m
        self.e = e

    def encrypt(self, data, offset=None, length=None):
        """Encrypts the given data with the current key"""
        if offset is None:
            offset = 0
        if length is None:
            length = len(data)

        with BinaryWriter() as writer:
            # Write SHA
            writer.write(sha1(data[offset:offset + length]).digest())
            # Write data
            writer.write(data[offset:offset + length])
            # Add padding if required
            if length < 235:
                writer.write(os.urandom(235 - length))

            result = int.from_bytes(writer.get_bytes(), byteorder='big')
            result = pow(result, self.e, self.m)

            # If the result byte count is less than 256, since the byte order is big,
            # the non-used bytes on the left will be 0 and act as padding,
            # without need of any additional checks
            return int.to_bytes(
                result, length=256, byteorder='big', signed=False)


class RSA:
    _server_keys = {
        '216be86c022bb4c3': RSAServerKey('216be86c022bb4c3', int(
            'C150023E2F70DB7985DED064759CFECF0AF328E69A41DAF4D6F01B538135A6F9'
            '1F8F8B2A0EC9BA9720CE352EFCF6C5680FFC424BD634864902DE0B4BD6D49F4E'
            '580230E3AE97D95C8B19442B3C0A10D8F5633FECEDD6926A7F6DAB0DDB7D457F'
            '9EA81B8465FCD6FFFEED114011DF91C059CAEDAF97625F6C96ECC74725556934'
            'EF781D866B34F011FCE4D835A090196E9A5F0E4449AF7EB697DDB9076494CA5F'
            '81104A305B6DD27665722C46B60E5DF680FB16B210607EF217652E60236C255F'
            '6A28315F4083A96791D7214BF64C1DF4FD0DB1944FB26A2A57031B32EEE64AD1'
            '5A8BA68885CDE74A5BFC920F6ABF59BA5C75506373E7130F9042DA922179251F',
            16), int('010001', 16))
    }

    @staticmethod
    def encrypt(fingerprint, data, offset=None, length=None):
        """Encrypts the given data given a fingerprint"""
        if fingerprint.lower() not in RSA._server_keys:
            return None

        key = RSA._server_keys[fingerprint.lower()]
        return key.encrypt(data, offset, length)
