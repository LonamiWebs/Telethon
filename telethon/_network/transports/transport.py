import abc


class Transport(abc.ABC):
    # Should return a newly-created instance of itself
    @abc.abstractmethod
    def recreate_fresh(self):
        pass

    @abc.abstractmethod
    def pack(self, input: bytes) -> bytes:
        pass

    # Should raise EOFError if it does not have enough bytes
    @abc.abstractmethod
    def unpack(self, input: bytes) -> (int, bytes):
        pass
