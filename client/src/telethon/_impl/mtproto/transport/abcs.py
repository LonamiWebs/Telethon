from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def pack(self, input: bytes, output: bytearray) -> None:
        pass

    @abstractmethod
    def unpack(self, input: bytes, output: bytearray) -> int:
        pass


class MissingBytes(ValueError):
    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"missing bytes, expected: {expected}, got: {got}")
