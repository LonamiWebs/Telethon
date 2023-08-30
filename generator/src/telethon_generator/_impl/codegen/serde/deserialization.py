import struct
from itertools import groupby
from typing import Optional, Tuple

from ....tl_parser import Definition, NormalParameter, Parameter, Type
from ..fakefs import SourceWriter
from .common import inner_type_fmt, is_trivial, to_class_name, trivial_struct_fmt

# Some implementations choose to create these types by hand.
# For consistency, we instead special-case the generator.
SPECIAL_CASED_OBJECT_READS = {
    0xF35C6D01: "reader.read_remaining()",  # rpc_result
    0x5BB8E511: "reader.read(_bytes)",  # message
}


def reader_read_fmt(ty: Type, constructor_id: int) -> Tuple[str, Optional[str]]:
    if is_trivial(NormalParameter(ty=ty, flag=None)):
        fmt = trivial_struct_fmt(NormalParameter(ty=ty, flag=None))
        size = struct.calcsize(f"<{fmt}")
        return f"reader.read_fmt(f'<{fmt}', {size})[0]", None
    elif ty.name == "string":
        return f"str(reader.read_bytes(), 'utf-8', 'replace')", None
    elif ty.name == "bytes":
        return f"reader.read_bytes()", None
    elif ty.name == "int128":
        return f"int.from_bytes(reader.read(16))", None
    elif ty.name == "int256":
        return f"int.from_bytes(reader.read(32))", None
    elif ty.bare:
        return f"{to_class_name(ty.name)}._read_from(reader)", None
    elif ty.name == "Object":
        try:
            return SPECIAL_CASED_OBJECT_READS[constructor_id], None
        except KeyError:
            raise NotImplementedError("missing special case for object read")
    else:
        return f"reader.read_serializable({inner_type_fmt(ty)})", "type-abstract"


def generate_normal_param_read(
    writer: SourceWriter, name: str, param: NormalParameter, constructor_id: int
) -> None:
    flag_check = f"_{param.flag.name} & {1 << param.flag.index}" if param.flag else None
    if param.ty.name == "true":
        if not flag_check:
            raise NotImplementedError("true parameter is expected to be a flag")
        writer.write(f"_{name} = ({flag_check}) != 0")
    elif param.ty.generic_ref:
        raise NotImplementedError("generic_ref deserialization not implemented")
    else:
        if flag_check:
            writer.write(f"if {flag_check}:")
            writer.indent()

        if param.ty.generic_arg:
            if param.ty.name not in ("Vector", "vector"):
                raise NotImplementedError(
                    "generic_arg deserialization for non-vectors not implemented"
                )

            if param.ty.bare:
                writer.write(f"__len = reader.read_fmt('<i', 4)[0]")
                writer.write(f"assert __len >= 0")
            else:
                writer.write(f"__vid, __len = reader.read_fmt('<ii', 8)")
                writer.write(f"assert __vid == 0x1cb5c415 and __len >= 0")

            generic = NormalParameter(ty=param.ty.generic_arg, flag=None)
            if is_trivial(generic):
                fmt = trivial_struct_fmt(generic)
                size = struct.calcsize(f"<{fmt}")
                writer.write(
                    f"_{name} = [*reader.read_fmt(f'<{{__len}}{fmt}', __len * {size})]"
                )
                if param.ty.generic_arg.name == "Bool":
                    writer.write(
                        f"assert all(__x in (0xbc799737, 0x0x997275b5) for __x in _{name})"
                    )
                    writer.write(f"_{name} = [_{name} == 0x997275b5]")
            else:
                fmt_read, type_ignore = reader_read_fmt(
                    param.ty.generic_arg, constructor_id
                )
                comment = f"  # type: ignore [{type_ignore}]" if type_ignore else ""
                writer.write(f"_{name} = [{fmt_read} for _ in range(__len)]{comment}")
        else:
            fmt_read, type_ignore = reader_read_fmt(param.ty, constructor_id)
            comment = f"  # type: ignore [{type_ignore}]" if type_ignore else ""
            writer.write(f"_{name} = {fmt_read}{comment}")

        if flag_check:
            writer.dedent()
            writer.write(f"else:")
            writer.write(f"  _{name} = None")


def generate_read(writer: SourceWriter, defn: Definition) -> None:
    for trivial, iter in groupby(
        defn.params,
        key=lambda p: is_trivial(p.ty),
    ):
        if trivial:
            # As an optimization, struct.unpack can handle more than one element at a time.
            group = list(iter)
            names = "".join(f"_{param.name}, " for param in group)
            fmt = "".join(trivial_struct_fmt(param.ty) for param in group)
            size = struct.calcsize(f"<{fmt}")
            writer.write(f"{names}= reader.read_fmt('<{fmt}', {size})")
            for param in group:
                if isinstance(param.ty, NormalParameter) and param.ty.ty.name == "Bool":
                    writer.write(f"assert _{param.name} in (0x997275b5, 0xbc799737)")
        else:
            for param in iter:
                if not isinstance(param.ty, NormalParameter):
                    raise RuntimeError("FlagsParameter should be considered trivial")
                generate_normal_param_read(writer, param.name, param.ty, defn.id)


def param_value_fmt(param: Parameter) -> str:
    if isinstance(param.ty, NormalParameter) and param.ty.ty.name == "Bool":
        return f"_{param.name} == 0x997275b5"
    else:
        return f"_{param.name}"
