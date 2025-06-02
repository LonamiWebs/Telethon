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

    @abstractmethod
    def reset(self):
        pass


class MissingBytesError(ValueError):
    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"missing bytes, expected: {expected}, got: {got}")


class BadLenError(ValueError):
    def __init__(self, *, got: int) -> None:
        super().__init__(f"bad len (got {got})")


class BadSeqError(ValueError):
    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"bad seq (expected {expected}, got {got})")


class BadCrcError(ValueError):
    def __init__(self, *, expected: int, got: int) -> None:
        super().__init__(f"bad crc (expected {expected}, got {got})")


class BadStatusError(ValueError):
    def __init__(self, *, status: int) -> None:
        super().__init__(f"bad status (negative length -{status})")
        self.status = status


TransportError = (
    MissingBytesError | BadLenError | BadSeqError | BadCrcError | BadStatusError
)
