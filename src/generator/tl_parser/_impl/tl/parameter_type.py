from abc import ABC
from dataclasses import dataclass
from typing import Optional, Union

from .flag import Flag
from .ty import Type


class BaseParameter(ABC):
    @staticmethod
    def from_str(ty: str) -> Union["FlagsParameter", "NormalParameter"]:
        if not ty:
            raise ValueError("empty")
        if ty == "#":
            return FlagsParameter()
        if (pos := ty.find("?")) != -1:
            ty, flag = ty[pos + 1 :], Flag.from_str(ty[:pos])
        else:
            flag = None
        return NormalParameter(ty=Type.from_str(ty), flag=flag)


@dataclass
class FlagsParameter(BaseParameter):
    def __str__(self) -> str:
        return "#"


@dataclass
class NormalParameter(BaseParameter):
    ty: Type
    flag: Optional[Flag]

    def __str__(self) -> str:
        res = ""
        if self.flag is not None:
            res += f"{self.flag}?"
        res += str(self.ty)
        return res
