import os
from hashlib import sha1
try:
    from Crypto.PublicKey import RSA
except ImportError:
    raise ImportError('Missing module "pycrypto", please install via pip.')

from ..extensions import BinaryWriter


# {fingerprint: Crypto.PublicKey.RSA._RSAobj} dictionary
_server_keys = { }


def get_byte_array(integer):
    """Return the variable length bytes corresponding to the given int"""
    # Operate in big endian (unlike most of Telegram API) since:
    # > "...pq is a representation of a natural number
    #    (in binary *big endian* format)..."
    # > "...current value of dh_prime equals
    #    (in *big-endian* byte order)..."
    # Reference: https://core.telegram.org/mtproto/auth_key
    return int.to_bytes(
        integer,
        length=(integer.bit_length() + 8 - 1) // 8,  # 8 bits per byte,
        byteorder='big',
        signed=False
    )


def _compute_fingerprint(key):
    """For a given Crypto.RSA key, computes its 8-bytes-long fingerprint
       in the same way that Telegram does.
    """
    with BinaryWriter() as writer:
        writer.tgwrite_bytes(get_byte_array(key.n))
        writer.tgwrite_bytes(get_byte_array(key.e))
        # Telegram uses the last 8 bytes as the fingerprint
        return sha1(writer.get_bytes()).digest()[-8:]


def add_key(pub):
    """Adds a new public key to be used when encrypting new data is needed"""
    global _server_keys
    key = RSA.importKey(pub)
    _server_keys[_compute_fingerprint(key)] = key


def encrypt(fingerprint, data):
    """Given the fingerprint of a previously added RSA key, encrypt its data
       in the way Telegram requires us to do so (sha1(data) + data + padding)
    """
    global _server_keys
    key = _server_keys.get(fingerprint, None)
    if not key:
        return None

    # len(sha1.digest) is always 20, so we're left with 255 - 20 - x padding
    to_encrypt = sha1(data).digest() + data + os.urandom(235 - len(data))
    return key.encrypt(to_encrypt, 0)[0]


# Add default keys
for pub in (
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAwVACPi9w23mF3tBkdZz+zwrzKOaaQdr01vAbU4E1pvkfj4sqDsm6
lyDONS789sVoD/xCS9Y0hkkC3gtL1tSfTlgCMOOul9lcixlEKzwKENj1Yz/s7daS
an9tqw3bfUV/nqgbhGX81v/+7RFAEd+RwFnK7a+XYl9sluzHRyVVaTTveB2GazTw
Efzk2DWgkBluml8OREmvfraX3bkHZJTKX4EQSjBbbdJ2ZXIsRrYOXfaA+xayEGB+
8hdlLmAjbCVfaigxX0CDqWeR1yFL9kwd9P0NsZRPsmoqVwMbMu7mStFai6aIhc3n
Slv8kg9qv1m6XHVQY3PnEw+QQtqSIXklHwIDAQAB
-----END RSA PUBLIC KEY-----''',
):
    add_key(pub)
