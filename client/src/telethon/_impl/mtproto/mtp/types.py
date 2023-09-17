import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, NewType, Optional, Self, Tuple

from ...tl.mtproto.types import RpcError as GeneratedRpcError

MsgId = NewType("MsgId", int)


class RpcError(ValueError):
    """
    A Remote Procedure Call Error.

    Only occurs when the answer to a request sent to Telegram is not the expected result.
    The library will never construct instances of this error by itself.

    This is the parent class of all :data:`telethon.errors` subtypes.

    .. seealso::

        :doc:`/concepts/errors`
    """

    def __init__(
        self,
        *,
        code: int = 0,
        name: str = "",
        value: Optional[int] = None,
        caused_by: Optional[int] = None,
    ) -> None:
        append_value = f" ({value})" if value else ""
        super().__init__(f"rpc error {code}: {name}{append_value}")

        self._code = code
        self._name = name
        self._value = value
        self._caused_by = caused_by

    @property
    def code(self) -> int:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> Optional[int]:
        return self._value

    @classmethod
    def _from_mtproto_error(cls, error: GeneratedRpcError) -> Self:
        if m := re.search(r"-?\d+", error.error_message):
            name = re.sub(
                r"_{2,}",
                "_",
                error.error_message[: m.start()] + error.error_message[m.end() :],
            ).strip("_")
            value = int(m[0])
        else:
            name = error.error_message
            value = None

        return cls(
            code=error.error_code,
            name=name,
            value=value,
            caused_by=None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return (
            self._code == other._code
            and self._name == other._name
            and self._value == other._value
        )


class BadMessage(ValueError):
    def __init__(
        self,
        *,
        code: int,
        caused_by: Optional[int] = None,
    ) -> None:
        super().__init__(f"bad msg: {code}")

        self._code = code
        self._caused_by = caused_by

    @property
    def code(self) -> int:
        return self._code

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._code == other._code


RpcResult = bytes | RpcError | BadMessage


@dataclass
class Deserialization:
    rpc_results: List[Tuple[MsgId, RpcResult]]
    updates: List[bytes]


# https://core.telegram.org/mtproto/description
class Mtp(ABC):
    @abstractmethod
    def push(self, request: bytes) -> Optional[MsgId]:
        pass

    @abstractmethod
    def finalize(self) -> bytes:
        pass

    @abstractmethod
    def deserialize(self, payload: bytes) -> Deserialization:
        pass
