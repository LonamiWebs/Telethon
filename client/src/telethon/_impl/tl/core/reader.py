import struct
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar

if TYPE_CHECKING:
    from .serializable import Serializable


T = TypeVar("T", bound="Serializable")


def _bootstrap_get_ty(constructor_id: int) -> Optional[Type["Serializable"]]:
    # Lazy import because generate code depends on the Reader.
    # After the first call, the class method is replaced with direct access.
    if Reader._get_ty is _bootstrap_get_ty:
        from ..layer import TYPE_MAPPING as API_TYPES
        from ..mtproto.layer import TYPE_MAPPING as MTPROTO_TYPES

        if API_TYPES.keys() & MTPROTO_TYPES.keys():
            raise RuntimeError(
                "generated api and mtproto schemas cannot have colliding constructor identifiers"
            )
        ALL_TYPES = API_TYPES | MTPROTO_TYPES

        # Signatures don't fully match, but this is a private method
        # and all previous uses are compatible with `dict.get`.
        Reader._get_ty = ALL_TYPES.get  # type: ignore [assignment]

    return Reader._get_ty(constructor_id)


class Reader:
    __slots__ = ("_view", "_pos", "_len")

    def __init__(self, buffer: bytes | memoryview) -> None:
        self._view = (
            memoryview(buffer) if not isinstance(buffer, memoryview) else buffer
        )
        self._pos = 0
        self._len = len(self._view)

    def read_remaining(self) -> memoryview:
        return self.read(self._len - self._pos)

    def read(self, n: int) -> memoryview:
        self._pos += n
        assert self._pos <= self._len
        return self._view[self._pos - n : self._pos]

    def read_fmt(self, fmt: str, size: int) -> tuple[Any, ...]:
        assert struct.calcsize(fmt) == size
        self._pos += size
        assert self._pos <= self._len
        return struct.unpack(fmt, self._view[self._pos - size : self._pos])

    def read_bytes(self) -> memoryview:
        if self._view[self._pos] == 254:
            self._pos += 4
            length = struct.unpack("<i", self._view[self._pos - 4 : self._pos])[0] >> 8
            padding = length % 4
        else:
            length = self._view[self._pos]
            padding = (length + 1) % 4
            self._pos += 1

        self._pos += length
        assert self._pos <= self._len
        data = self._view[self._pos - length : self._pos]
        if padding > 0:
            self._pos += 4 - padding

        return data

    _get_ty = staticmethod(_bootstrap_get_ty)

    def read_serializable(self, cls: Type[T]) -> T:
        # Calls to this method likely need to ignore "type-abstract".
        # See https://github.com/python/mypy/issues/4717.
        # Unfortunately `typing.cast` would add a tiny amount of runtime overhead
        # which cannot be removed with optimization enabled.
        self._pos += 4
        assert self._pos <= self._len
        cid = struct.unpack("<I", self._view[self._pos - 4 : self._pos])[0]
        ty = self._get_ty(cid)
        if ty is None:
            raise ValueError(f"No type found for constructor ID: {cid:x}")
        assert issubclass(ty, cls)
        return ty._read_from(self)
