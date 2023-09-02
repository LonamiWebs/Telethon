import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, NewType, Optional, Self, Tuple

from ...tl.mtproto.types import RpcError as GeneratedRpcError

MsgId = NewType("MsgId", int)


class RpcError(ValueError):
    def __init__(
        self,
        *,
        code: int = 0,
        name: str = "",
        value: Optional[int] = None,
        caused_by: Optional[int] = None,
    ) -> None:
        append_value = f" ({value})" if value else None
        super().__init__(f"rpc error {code}: {name}{append_value}")

        self.code = code
        self.name = name
        self.value = value
        self.caused_by = caused_by

    @classmethod
    def from_mtproto_error(cls, error: GeneratedRpcError) -> Self:
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
            self.code == other.code
            and self.name == other.name
            and self.value == other.value
        )


class BadMessage(ValueError):
    def __init__(
        self,
        *,
        code: int,
        caused_by: Optional[int] = None,
    ) -> None:
        super().__init__(f"bad msg: {code}")

        self.code = code
        self.caused_by = caused_by

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.code == other.code


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
