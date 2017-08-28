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
        self.iv = iv
        self._aes._counter._counter = list(self.iv)

    def reset(self):
        pass

    def encrypt(self, data):
        result = self._aes.encrypt(data)
        self.reset()
        return result

    def decrypt(self, data):
        result = self._aes.decrypt(data)
        self.reset()
        return result
