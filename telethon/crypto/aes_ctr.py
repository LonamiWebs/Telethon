import pyaes


class AESModeCTR:
    """Wrapper around pyaes.AESModeOfOperationCTR mode with custom IV"""
    # TODO Maybe make a pull request to pyaes to support iv on CTR

    def __init__(self, key, iv):
        # TODO Use libssl if available
        assert isinstance(key, bytes)
        self._aes = pyaes.AESModeOfOperationCTR(key)

        assert isinstance(iv, bytes)
        assert len(iv) == 16
        self._aes._counter._counter = list(iv)

    def encrypt(self, data):
        return self._aes.encrypt(data)

    def decrypt(self, data):
        return self._aes.decrypt(data)
