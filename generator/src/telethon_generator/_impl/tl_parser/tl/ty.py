from dataclasses import dataclass
from typing import Iterator, List, Optional, Self


@dataclass
class Type:
    namespace: List[str]
    name: str
    bare: bool
    generic_ref: bool
    generic_arg: Optional[Self]

    @classmethod
    def from_str(cls, ty: str) -> Self:
        stripped = ty.lstrip("!")
        ty, generic_ref = stripped, stripped != ty

        if (pos := ty.find("<")) != -1:
            if not ty.endswith(">"):
                raise ValueError("invalid generic")
            ty, generic_arg = ty[:pos], Type.from_str(ty[pos + 1 : -1])
        else:
            generic_arg = None

        namespace = ty.split(".")
        if not all(namespace):
            raise ValueError("empty")

        name = namespace.pop()
        bare = name[0].islower()

        return cls(
            namespace=namespace,
            name=name,
            bare=bare,
            generic_ref=generic_ref,
            generic_arg=generic_arg,
        )

    @property
    def full_name(self) -> str:
        ns = ".".join(self.namespace) + "." if self.namespace else ""
        return f"{ns}{self.name}"

    def __str__(self) -> str:
        res = ""
        for ns in self.namespace:
            res += f"{ns}."
        if self.generic_ref:
            res += "!"
        res += self.name
        if self.generic_arg is not None:
            res += f"<{self.generic_arg}>"
        return res

    def find_generic_refs(self) -> Iterator[str]:
        if self.generic_ref:
            yield self.name
        if self.generic_arg is not None:
            yield from self.generic_arg.find_generic_refs()
