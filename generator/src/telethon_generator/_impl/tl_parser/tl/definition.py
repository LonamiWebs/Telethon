from dataclasses import dataclass
from typing import Self

from ..utils import infer_id
from .parameter import Parameter, TypeDefNotImplemented
from .parameter_type import FlagsParameter, NormalParameter
from .ty import Type


@dataclass
class Definition:
    namespace: list[str]
    name: str
    id: int
    params: list[Parameter]
    ty: Type

    @classmethod
    def from_str(cls, definition: str) -> Self:
        if not definition or definition.isspace():
            raise ValueError("empty")

        parts = definition.split("=")
        if len(parts) < 2:
            raise ValueError("missing type")

        left, ty_str, *_ = map(str.strip, parts)
        try:
            ty = Type.from_str(ty_str)
        except ValueError as e:
            if e.args[0] == "empty":
                raise ValueError("missing type")
            else:
                raise

        if (pos := left.find(" ")) != -1:
            name, middle = left[:pos], left[pos:].strip()
        else:
            name, middle = left.strip(), ""

        parts = name.split("#")
        if len(parts) < 2:
            name, id_str = parts[0], None
        else:
            name, id_str, *_ = parts

        namespace = name.split(".")
        if not all(namespace):
            raise ValueError("missing name")

        name = namespace.pop()

        if id_str is None:
            id = infer_id(definition)
        else:
            try:
                id = int(id_str, 16)
            except ValueError:
                raise ValueError("invalid id")

        type_defs: list[str] = []
        flag_defs: list[str] = []
        params: list[Parameter] = []

        for param_str in middle.split():
            try:
                param = Parameter.from_str(param_str)
            except TypeDefNotImplemented as e:
                type_defs.append(e.name)
                continue

            if isinstance(param.ty, FlagsParameter):
                flag_defs.append(param.name)
            elif not isinstance(param.ty, NormalParameter):
                raise TypeError(f"unrecognised subclass: {param.ty}")
            elif param.ty.ty.generic_ref and param.ty.ty.name not in type_defs:
                raise ValueError("missing def")
            elif param.ty.flag and param.ty.flag.name not in flag_defs:
                raise ValueError("missing def")

            params.append(param)

        if ty.name in type_defs:
            ty.generic_ref = True

        return cls(
            namespace=namespace,
            name=name,
            id=id,
            params=params,
            ty=ty,
        )

    @property
    def full_name(self) -> str:
        ns = ".".join(self.namespace) + "." if self.namespace else ""
        return f"{ns}{self.name}"

    def __str__(self) -> str:
        res = ""
        for ns in self.namespace:
            res += f"{ns}."
        res += f"{self.name}#{self.id:x}"

        def_set: set[str] = set()
        for param in self.params:
            if isinstance(param.ty, NormalParameter):
                def_set.update(param.ty.ty.find_generic_refs())

        type_defs = list(sorted(def_set))
        for type_def in type_defs:
            res += f" {{{type_def}:Type}}"

        for param in self.params:
            res += f" {param}"

        res += f" = {self.ty}"
        return res
