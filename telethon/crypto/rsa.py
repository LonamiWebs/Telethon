"""
This module holds several utilities regarding RSA and server fingerprints.
"""
import os
import struct
from hashlib import sha1
try:
    import rsa
    import rsa.core
except ImportError:
    rsa = None
    raise ImportError('Missing module "rsa", please install via pip.')

from ..tl import TLObject


# {fingerprint: (Crypto.PublicKey.RSA._RSAobj, old)} dictionary
_server_keys = {}


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
        (integer.bit_length() + 8 - 1) // 8,  # 8 bits per byte,
        byteorder='big',
        signed=False
    )


def _compute_fingerprint(key):
    """
    Given a RSA key, computes its fingerprint like Telegram does.

    :param key: the Crypto.RSA key.
    :return: its 8-bytes-long fingerprint.
    """
    n = TLObject.serialize_bytes(get_byte_array(key.n))
    e = TLObject.serialize_bytes(get_byte_array(key.e))
    # Telegram uses the last 8 bytes as the fingerprint
    return struct.unpack('<q', sha1(n + e).digest()[-8:])[0]


def add_key(pub, *, old):
    """Adds a new public key to be used when encrypting new data is needed"""
    global _server_keys
    key = rsa.PublicKey.load_pkcs1(pub)
    _server_keys[_compute_fingerprint(key)] = (key, old)


def encrypt(fingerprint, data, *, use_old=False):
    """
    Encrypts the given data known the fingerprint to be used
    in the way Telegram requires us to do so (sha1(data) + data + padding)

    :param fingerprint: the fingerprint of the RSA key.
    :param data: the data to be encrypted.
    :param use_old: whether old keys should be used.
    :return:
        the cipher text, or None if no key matching this fingerprint is found.
    """
    global _server_keys
    key, old = _server_keys.get(fingerprint, None)
    if (not key) or (old and not use_old):
        return None

    # len(sha1.digest) is always 20, so we're left with 255 - 20 - x padding
    to_encrypt = sha1(data).digest() + data + os.urandom(235 - len(data))

    # rsa module rsa.encrypt adds 11 bits for padding which we don't want
    # rsa module uses rsa.transform.bytes2int(to_encrypt), easier way:
    payload = int.from_bytes(to_encrypt, 'big')
    encrypted = rsa.core.encrypt_int(payload, key.e, key.n)
    # rsa module uses transform.int2bytes(encrypted, keylength), easier:
    block = encrypted.to_bytes(256, 'big')
    return block


# Add default keys
# https://github.com/DrKLO/Telegram/blob/a724d96e9c008b609fe188d122aa2922e40de5fc/TMessagesProj/jni/tgnet/Handshake.cpp#L356-L436
for pub in (
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAruw2yP/BCcsJliRoW5eBVBVle9dtjJw+OYED160Wybum9SXtBBLX
riwt4rROd9csv0t0OHCaTmRqBcQ0J8fxhN6/cpR1GWgOZRUAiQxoMnlt0R93LCX/
j1dnVa/gVbCjdSxpbrfY2g2L4frzjJvdl84Kd9ORYjDEAyFnEA7dD556OptgLQQ2
e2iVNq8NZLYTzLp5YpOdO1doK+ttrltggTCy5SrKeLoCPPbOgGsdxJxyz5KKcZnS
Lj16yE5HvJQn0CNpRdENvRUXe6tBP78O39oJ8BTHp9oIjd6XWXAsp2CvK45Ol8wF
XGF710w9lwCGNbmNxNYhtIkdqfsEcwR5JwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAvfLHfYH2r9R70w8prHblWt/nDkh+XkgpflqQVcnAfSuTtO05lNPs
pQmL8Y2XjVT4t8cT6xAkdgfmmvnvRPOOKPi0OfJXoRVylFzAQG/j83u5K3kRLbae
7fLccVhKZhY46lvsueI1hQdLgNV9n1cQ3TDS2pQOCtovG4eDl9wacrXOJTG2990V
jgnIKNA0UMoP+KF03qzryqIt3oTvZq03DyWdGK+AZjgBLaDKSnC6qD2cFY81UryR
WOab8zKkWAnhw2kFpcqhI0jdV5QaSCExvnsjVaX0Y1N0870931/5Jb9ICe4nweZ9
kSDF/gip3kWLG0o8XQpChDfyvsqB9OLV/wIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAs/ditzm+mPND6xkhzwFIz6J/968CtkcSE/7Z2qAJiXbmZ3UDJPGr
zqTDHkO30R8VeRM/Kz2f4nR05GIFiITl4bEjvpy7xqRDspJcCFIOcyXm8abVDhF+
th6knSU0yLtNKuQVP6voMrnt9MV1X92LGZQLgdHZbPQz0Z5qIpaKhdyA8DEvWWvS
Uwwc+yi1/gGaybwlzZwqXYoPOhwMebzKUk0xW14htcJrRrq+PXXQbRzTMynseCoP
Ioke0dtCodbA3qQxQovE16q9zz4Otv2k4j63cz53J+mhkVWAeWxVGI0lltJmWtEY
K6er8VqqWot3nqmWMXogrgRLggv/NbbooQIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAvmpxVY7ld/8DAjz6F6q05shjg8/4p6047bn6/m8yPy1RBsvIyvuD
uGnP/RzPEhzXQ9UJ5Ynmh2XJZgHoE9xbnfxL5BXHplJhMtADXKM9bWB11PU1Eioc
3+AXBB8QiNFBn2XI5UkO5hPhbb9mJpjA9Uhw8EdfqJP8QetVsI/xrCEbwEXe0xvi
fRLJbY08/Gp66KpQvy7g8w7VB8wlgePexW3pT13Ap6vuC+mQuJPyiHvSxjEKHgqe
Pji9NP3tJUFQjcECqcm0yV7/2d0t/pbCm+ZH1sadZspQCEPPrtbkQBlvHb4OLiIW
PGHKSMeRFvp3IWcmdJqXahxLCUS1Eh6MAQIDAQAB
-----END RSA PUBLIC KEY-----''',

):
    add_key(pub, old=False)


for pub in (
        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAwVACPi9w23mF3tBkdZz+zwrzKOaaQdr01vAbU4E1pvkfj4sqDsm6
lyDONS789sVoD/xCS9Y0hkkC3gtL1tSfTlgCMOOul9lcixlEKzwKENj1Yz/s7daS
an9tqw3bfUV/nqgbhGX81v/+7RFAEd+RwFnK7a+XYl9sluzHRyVVaTTveB2GazTw
Efzk2DWgkBluml8OREmvfraX3bkHZJTKX4EQSjBbbdJ2ZXIsRrYOXfaA+xayEGB+
8hdlLmAjbCVfaigxX0CDqWeR1yFL9kwd9P0NsZRPsmoqVwMbMu7mStFai6aIhc3n
Slv8kg9qv1m6XHVQY3PnEw+QQtqSIXklHwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAxq7aeLAqJR20tkQQMfRn+ocfrtMlJsQ2Uksfs7Xcoo77jAid0bRt
ksiVmT2HEIJUlRxfABoPBV8wY9zRTUMaMA654pUX41mhyVN+XoerGxFvrs9dF1Ru
vCHbI02dM2ppPvyytvvMoefRoL5BTcpAihFgm5xCaakgsJ/tH5oVl74CdhQw8J5L
xI/K++KJBUyZ26Uba1632cOiq05JBUW0Z2vWIOk4BLysk7+U9z+SxynKiZR3/xdi
XvFKk01R3BHV+GUKM2RYazpS/P8v7eyKhAbKxOdRcFpHLlVwfjyM1VlDQrEZxsMp
NTLYXb6Sce1Uov0YtNx5wEowlREH1WOTlwIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAsQZnSWVZNfClk29RcDTJQ76n8zZaiTGuUsi8sUhW8AS4PSbPKDm+
DyJgdHDWdIF3HBzl7DHeFrILuqTs0vfS7Pa2NW8nUBwiaYQmPtwEa4n7bTmBVGsB
1700/tz8wQWOLUlL2nMv+BPlDhxq4kmJCyJfgrIrHlX8sGPcPA4Y6Rwo0MSqYn3s
g1Pu5gOKlaT9HKmE6wn5Sut6IiBjWozrRQ6n5h2RXNtO7O2qCDqjgB2vBxhV7B+z
hRbLbCmW0tYMDsvPpX5M8fsO05svN+lKtCAuz1leFns8piZpptpSCFn7bWxiA9/f
x5x17D7pfah3Sy2pA+NDXyzSlGcKdaUmwQIDAQAB
-----END RSA PUBLIC KEY-----''',

        '''-----BEGIN RSA PUBLIC KEY-----
MIIBCgKCAQEAwqjFW0pi4reKGbkc9pK83Eunwj/k0G8ZTioMMPbZmW99GivMibwa
xDM9RDWabEMyUtGoQC2ZcDeLWRK3W8jMP6dnEKAlvLkDLfC4fXYHzFO5KHEqF06i
qAqBdmI1iBGdQv/OQCBcbXIWCGDY2AsiqLhlGQfPOI7/vvKc188rTriocgUtoTUc
/n/sIUzkgwTqRyvWYynWARWzQg0I9olLBBC2q5RQJJlnYXZwyTL3y9tdb7zOHkks
WV9IMQmZmyZh/N7sMbGWQpt4NMchGpPGeJ2e5gHBjDnlIf2p1yZOYeUYrdbwcS0t
UiggS4UeE8TzIuXFQxw7fzEIlmhIaq3FnwIDAQAB
-----END RSA PUBLIC KEY-----''',
):
    add_key(pub, old=True)
