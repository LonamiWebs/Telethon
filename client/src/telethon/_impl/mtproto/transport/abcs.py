from abc import ABC, abstractmethod
from collections.abc import Callable

OutFn = Callable[[bytes | bytearray | memoryview], None]


class Transport(ABC):
    # Python's stream writer has a synchronous write (buffer append) followed
    # by drain. The buffer is externally managed, so `write` is used as input.
    @abstractmethod
    def pack(self, input: bytes, write: OutFn) -> None:
        pass

    @abstractmethod
    def unpack(self, input: bytes | bytearray | memoryview, output: bytearray) -> int:
        pass


class MissingBytesError(ValueError):
    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"missing bytes, expected: {expected}, got: {got}")


class BadStatusError(ValueError):
    def __init__(self, *, status: int) -> None:
        super().__init__(f"transport reported bad status: {status}")
        self.status = status
