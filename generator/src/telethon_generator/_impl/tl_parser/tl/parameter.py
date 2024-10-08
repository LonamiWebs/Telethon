from dataclasses import dataclass

from typing_extensions import Self

from .parameter_type import BaseParameter


class TypeDefNotImplementedError(NotImplementedError):
    def __init__(self, name: str) -> None:
        super().__init__(f"typedef not implemented: {name}")
        self.name = name


@dataclass
class Parameter:
    name: str
    ty: BaseParameter

    @classmethod
    def from_str(cls, param: str) -> Self:
        if param.startswith("{"):
            if param.endswith(":Type}"):
                raise TypeDefNotImplementedError(param[1 : param.index(":")])
            else:
                raise ValueError("missing def")

        parts = param.split(":")
        if not parts:
            raise ValueError("empty")
        elif len(parts) == 1:
            raise ValueError("not implemented")
        else:
            name, ty, *_ = parts

        if not name:
            raise ValueError("empty")

        return cls(name=name, ty=BaseParameter.from_str(ty))

    def __str__(self) -> str:
        return f"{self.name}:{self.ty}"
