"""
This module holds the AESModeCTR wrapper class.
"""
import pyaes
import logging


__log__ = logging.getLogger(__name__)


try:
    import tgcrypto
    __log__.debug('tgcrypto detected, it will be used for ctr encryption')
except ImportError:
    tgcrypto = None
    __log__.debug('tgcrypto module not installed, '
                'falling back to (slower) Python encryption')


class AESModeCTR:
    """Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV"""
    # TODO Maybe make a pull request to pyaes to support iv on CTR

    def __init__(self, key, iv):
        """
        Initializes the AES CTR mode with the given key/iv pair.

        :param key: the key to be used as bytes.
        :param iv: the bytes initialization vector. Must have a length of 16.
        """
        # TODO Use libssl if available
        if tgcrypto:
            self._aes = (key, iv, bytearray(1))
        else:
            assert isinstance(key, bytes)
            self._aes = pyaes.AESModeOfOperationCTR(key)

            assert isinstance(iv, bytes)
            assert len(iv) == 16
            self._aes._counter._counter = list(iv)

    def encrypt(self, data):
        """
        Encrypts the given plain text through AES CTR.

        :param data: the plain text to be encrypted.
        :return: the encrypted cipher text.
        """
        if tgcrypto:
            return tgcrypto.ctr256_encrypt(data, *self._aes)
        return self._aes.encrypt(data)

    def decrypt(self, data):
        """
        Decrypts the given cipher text through AES CTR

        :param data: the cipher text to be decrypted.
        :return: the decrypted plain text.
        """
        if tgcrypto:
            return tgcrypto.ctr256_decrypt(data, *self._aes)
        return self._aes.decrypt(data)
