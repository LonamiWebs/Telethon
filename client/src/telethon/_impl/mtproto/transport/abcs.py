from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def pack(self, input: bytes, output: bytearray) -> None:
        pass

    @abstractmethod
    def unpack(self, input: bytes, output: bytearray) -> None:
        pass
