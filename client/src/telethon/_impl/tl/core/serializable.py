import abc
import struct
from typing import Protocol

from typing_extensions import Self

from .reader import Reader


class HasSlots(Protocol):
    __slots__: tuple[str, ...]


def obj_repr(self: HasSlots) -> str:
    fields = ((attr, getattr(self, attr)) for attr in self.__slots__)
    params = ", ".join(f"{name}={field!r}" for name, field in fields)
    return f"{self.__class__.__name__}({params})"


class Serializable(abc.ABC):
    __slots__: tuple[str, ...] = ()

    @classmethod
    @abc.abstractmethod
    def constructor_id(cls) -> int:
        pass

    @classmethod
    def _read_from(cls, reader: Reader) -> Self:
        return reader.read_serializable(cls)

    def _write_boxed_to(self, buffer: bytearray) -> None:
        buffer += struct.pack("<I", self.constructor_id())
        self._write_to(buffer)

    @abc.abstractmethod
    def _write_to(self, buffer: bytearray) -> None:
        pass

    @classmethod
    def from_bytes(cls, blob: bytes | bytearray | memoryview) -> Self:
        return Reader(blob).read_serializable(cls)

    def __bytes__(self) -> bytes:
        buffer = bytearray()
        self._write_boxed_to(buffer)
        return bytes(buffer)

    __repr__ = obj_repr

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return all(
            getattr(self, attr) == getattr(other, attr) for attr in self.__slots__
        )


def serialize_bytes_to(buffer: bytearray, data: bytes | bytearray | memoryview) -> None:
    length = len(data)
    if length < 0xFE:
        buffer += struct.pack("<B", length)
        length += 1
    else:
        buffer += b"\xfe"
        buffer += struct.pack("<i", length)[:-1]

    buffer += data
    buffer += bytes((4 - (length % 4)) % 4)
