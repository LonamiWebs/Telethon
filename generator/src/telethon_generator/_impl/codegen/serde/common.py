import re
from typing import Iterator

from ....tl_parser import BaseParameter, FlagsParameter, NormalParameter, Type


def to_class_name(name: str) -> str:
    return re.sub(r"(?:^|_)([a-z])", lambda m: m[1].upper(), name)


def to_method_name(name: str) -> str:
    snake_case = re.sub(
        r"_+[A-Za-z]+|[A-Z]*[a-z]+", lambda m: "_" + m[0].replace("_", "").lower(), name
    )
    return snake_case.strip("_")


def gen_tmp_names() -> Iterator[str]:
    i = 0
    while True:
        yield f"_t{i}"
        i += 1


def is_computed(ty: BaseParameter) -> bool:
    return isinstance(ty, FlagsParameter)


def is_trivial(ty: BaseParameter) -> bool:
    return (
        isinstance(ty, FlagsParameter)
        or isinstance(ty, NormalParameter)
        and not ty.flag
        and ty.ty.name in ("int", "long", "double", "Bool")
    )


_TRIVIAL_STRUCT_MAP = {"int": "i", "long": "q", "double": "d", "Bool": "I"}


def trivial_struct_fmt(ty: BaseParameter) -> str:
    try:
        return (
            _TRIVIAL_STRUCT_MAP[ty.ty.name] if isinstance(ty, NormalParameter) else "I"
        )
    except KeyError:
        raise ValueError("input param was not trivial")


_INNER_TYPE_MAP = {
    "Bool": "bool",
    "true": "bool",
    "int": "int",
    "long": "int",
    "int128": "int",
    "int256": "int",
    "double": "float",
    "bytes": "bytes",
    "string": "str",
}


def inner_type_fmt(ty: Type) -> str:
    builtin_ty = _INNER_TYPE_MAP.get(ty.name)

    if builtin_ty:
        return builtin_ty
    elif ty.bare:
        return to_class_name(ty.name)
    elif ty.generic_ref:
        return "bytes"
    else:
        ns = (".".join(ty.namespace) + ".") if ty.namespace else ""
        return f"abcs.{ns}{to_class_name(ty.name)}"


def param_type_fmt(ty: BaseParameter) -> str:
    if isinstance(ty, FlagsParameter):
        return "int"
    elif not isinstance(ty, NormalParameter):
        raise TypeError("unexpected input type {ty}")

    inner_ty: Type
    if ty.ty.generic_arg:
        if ty.ty.name not in ("Vector", "vector"):
            raise NotImplementedError(
                "generic_arg type for non-vectors not implemented"
            )

        inner_ty = ty.ty.generic_arg
    else:
        inner_ty = ty.ty

    res = inner_type_fmt(inner_ty)

    if ty.ty.generic_arg:
        res = f"List[{res}]"

    if ty.flag and ty.ty.name != "true":
        res = f"Optional[{res}]"

    return res
