import os
import ctypes
from ctypes.util import find_library

# search and load libssl.so
lib = find_library('ssl')
if not lib:
    raise ImportError('libssl.so not found')
libssl = ctypes.cdll.LoadLibrary(lib)

""" <aes.h>
# define AES_ENCRYPT     1
# define AES_DECRYPT     0
# define AES_MAXNR 14
struct aes_key_st {
# ifdef AES_LONG
    unsigned long rd_key[4 * (AES_MAXNR + 1)];
# else
    unsigned int rd_key[4 * (AES_MAXNR + 1)];
# endif
    int rounds;
};
typedef struct aes_key_st AES_KEY;

int AES_set_encrypt_key(const unsigned char *userKey, const int bits,
                        AES_KEY *key);
int AES_set_decrypt_key(const unsigned char *userKey, const int bits,
                        AES_KEY *key);
void AES_ige_encrypt(const unsigned char *in, unsigned char *out,
                     size_t length, const AES_KEY *key,
                     unsigned char *ivec, const int enc);
"""

AES_MAXNR = 14
AES_ENCRYPT = ctypes.c_int(1)
AES_DECRYPT = ctypes.c_int(0)

class AES_KEY(ctypes.Structure):
    _fields_ = [
        ('rd_key', ctypes.c_uint32 * (4*(AES_MAXNR + 1))),
        ('rounds', ctypes.c_uint),
    ]

class AES:
    @staticmethod
    def decrypt_ige(cipher_text, key, iv):

        # declare types
        aeskey = AES_KEY()
        ckey = (ctypes.c_ubyte * len(key))(*key)
        cklen = ctypes.c_int(len(key)*8)
        cin = (ctypes.c_ubyte * len(cipher_text))(*cipher_text)
        ctlen = ctypes.c_size_t(len(cipher_text))
        cout = (ctypes.c_ubyte * len(cipher_text))()
        civ = (ctypes.c_ubyte * len(iv))(*iv)

        # decrypt
        libssl.AES_set_decrypt_key(ckey, cklen,  ctypes.byref(aeskey))
        libssl.AES_ige_encrypt(ctypes.byref(cin), ctypes.byref(cout), ctlen,  ctypes.byref(aeskey), ctypes.byref(civ), AES_DECRYPT)

        return bytes(cout)

    @staticmethod
    def encrypt_ige(plain_text, key, iv):

        # Add random padding if and only if it's not evenly divisible by 16 already
        if len(plain_text) % 16 != 0:
            padding_count = 16 - len(plain_text) % 16
            plain_text += os.urandom(padding_count)

        # declare types
        aeskey = AES_KEY()
        ckey = (ctypes.c_ubyte * len(key))(*key)
        cklen = ctypes.c_int(len(key)*8)
        cin = (ctypes.c_ubyte * len(plain_text))(*plain_text)
        ctlen = ctypes.c_size_t(len(plain_text))
        cout = (ctypes.c_ubyte * len(plain_text))()
        civ = (ctypes.c_ubyte * len(iv))(*iv)

        # encrypt
        libssl.AES_set_encrypt_key(ckey, cklen,  ctypes.byref(aeskey))
        libssl.AES_ige_encrypt(ctypes.byref(cin), ctypes.byref(cout), ctlen,  ctypes.byref(aeskey), ctypes.byref(civ), AES_ENCRYPT)

        return bytes(cout)
