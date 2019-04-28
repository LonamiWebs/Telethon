"""
Helper module around the system's libssl library if available for IGE mode.
"""
import ctypes
import ctypes.util
import logging


__log__ = logging.getLogger(__name__)


lib = ctypes.util.find_library('ssl')
try:
    if not lib:
        raise OSError('no library called "ssl" found')

    _libssl = ctypes.cdll.LoadLibrary(lib)
except OSError as e:
    # See https://github.com/LonamiWebs/Telethon/issues/1167
    # Sometimes `find_library` returns improper filenames.
    __log__.info('Failed to load %s: %s (%s)', lib, type(e), e)
    _libssl = None

if not _libssl:
    decrypt_ige = None
    encrypt_ige = None
else:
    # https://github.com/openssl/openssl/blob/master/include/openssl/aes.h
    AES_ENCRYPT = ctypes.c_int(1)
    AES_DECRYPT = ctypes.c_int(0)
    AES_MAXNR = 14

    class AES_KEY(ctypes.Structure):
        """Helper class representing an AES key"""
        _fields_ = [
            ('rd_key', ctypes.c_uint32 * (4 * (AES_MAXNR + 1))),
            ('rounds', ctypes.c_uint),
        ]

    def decrypt_ige(cipher_text, key, iv):
        aes_key = AES_KEY()
        key_len = ctypes.c_int(8 * len(key))
        key = (ctypes.c_ubyte * len(key))(*key)
        iv = (ctypes.c_ubyte * len(iv))(*iv)

        in_len = ctypes.c_size_t(len(cipher_text))
        in_ptr = (ctypes.c_ubyte * len(cipher_text))(*cipher_text)
        out_ptr = (ctypes.c_ubyte * len(cipher_text))()

        _libssl.AES_set_decrypt_key(key, key_len, ctypes.byref(aes_key))
        _libssl.AES_ige_encrypt(
            ctypes.byref(in_ptr),
            ctypes.byref(out_ptr),
            in_len,
            ctypes.byref(aes_key),
            ctypes.byref(iv),
            AES_DECRYPT
        )

        return bytes(out_ptr)

    def encrypt_ige(plain_text, key, iv):
        aes_key = AES_KEY()
        key_len = ctypes.c_int(8 * len(key))
        key = (ctypes.c_ubyte * len(key))(*key)
        iv = (ctypes.c_ubyte * len(iv))(*iv)

        in_len = ctypes.c_size_t(len(plain_text))
        in_ptr = (ctypes.c_ubyte * len(plain_text))(*plain_text)
        out_ptr = (ctypes.c_ubyte * len(plain_text))()

        _libssl.AES_set_encrypt_key(key, key_len, ctypes.byref(aes_key))
        _libssl.AES_ige_encrypt(
            ctypes.byref(in_ptr),
            ctypes.byref(out_ptr),
            in_len,
            ctypes.byref(aes_key),
            ctypes.byref(iv),
            AES_ENCRYPT
        )

        return bytes(out_ptr)
