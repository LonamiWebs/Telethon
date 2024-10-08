from dataclasses import dataclass

from typing_extensions import Self


@dataclass
class Flag:
    name: str
    index: int

    @classmethod
    def from_str(cls, ty: str) -> Self:
        if (dot_pos := ty.find(".")) != -1:
            try:
                index = int(ty[dot_pos + 1 :])
            except ValueError:
                raise ValueError("invalid flag")
            else:
                return cls(name=ty[:dot_pos], index=index)
        else:
            raise ValueError("invalid flag")

    def __str__(self) -> str:
        return f"{self.name}.{self.index}"
