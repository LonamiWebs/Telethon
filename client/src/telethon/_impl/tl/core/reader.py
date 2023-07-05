import struct
from typing import TYPE_CHECKING, Any, Type, TypeVar

if TYPE_CHECKING:
    from .serializable import Serializable


T = TypeVar("T", bound="Serializable")


class Reader:
    __slots__ = ("_buffer", "_pos", "_view")

    def __init__(self, buffer: bytes) -> None:
        self._buffer = buffer
        self._pos = 0
        self._view = memoryview(self._buffer)

    def read(self, n: int) -> bytes:
        self._pos += n
        return self._view[self._pos - n : n]

    def read_fmt(self, fmt: str, size: int) -> tuple[Any, ...]:
        assert struct.calcsize(fmt) == size
        self._pos += size
        return struct.unpack(fmt, self._view[self._pos - size : self._pos])

    def read_bytes(self) -> bytes:
        if self._buffer[self._pos] == 254:
            self._pos += 4
            (length,) = struct.unpack(
                "<i", self._buffer[self._pos - 3 : self._pos] + b"\0"
            )
            padding = length % 4
        else:
            length = self._buffer[self._pos]
            padding = (length + 1) % 4
            self._pos += 1

        self._pos += length
        data = self._view[self._pos - length : self._pos]
        if padding > 0:
            self._pos += 4 - padding

        return data

    @staticmethod
    def _get_ty(_: int) -> Type["Serializable"]:
        # Implementation replaced during import to prevent cycles,
        # without the performance hit of having the import inside.
        raise NotImplementedError

    def read_serializable(self, cls: Type[T]) -> T:
        # Calls to this method likely need to ignore "type-abstract".
        # See https://github.com/python/mypy/issues/4717.
        # Unfortunately `typing.cast` would add a tiny amount of runtime overhead
        # which cannot be removed with optimization enabled.
        self._pos += 4
        cid = struct.unpack("<I", self._view[self._pos - 4 : self._pos])[0]
        ty = self._get_ty(cid)
        if ty is None:
            raise ValueError(f"No type found for constructor ID: {cid:x}")
        assert issubclass(ty, cls)
        return ty._read_from(self)
