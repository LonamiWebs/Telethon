import re
from typing import Iterator, List

from ....tl_parser import BaseParameter, FlagsParameter, NormalParameter, Type


def split_words(name: str) -> List[str]:
    return re.findall(
        r"""
        ^$
        |[a-z\d]+
        |[A-Z][A-Z\d]+(?=[A-Z]|_|$)
        |[A-Z][a-z\d]+
        """,
        name,
        re.VERBOSE,
    )


def to_class_name(name: str) -> str:
    return "".join(word.title() for word in split_words(name))


def to_method_name(name: str) -> str:
    return "_".join(word.lower() for word in split_words(name))


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
    elif ty.name == "Object":
        return "Serializable"
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

    res = "bytes" if inner_ty.name == "Object" else inner_type_fmt(inner_ty)

    if ty.ty.generic_arg:
        res = f"List[{res}]"

    if ty.flag and ty.ty.name != "true":
        res = f"Optional[{res}]"

    return res
