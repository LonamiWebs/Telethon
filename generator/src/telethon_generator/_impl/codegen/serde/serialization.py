import struct
from collections.abc import Iterator
from itertools import groupby

from ....tl_parser import Definition, FlagsParameter, NormalParameter, Parameter, Type
from ..fakefs import SourceWriter
from .common import gen_tmp_names, is_computed, is_trivial, sanitize_name, trivial_struct_fmt


def param_value_expr(param: Parameter) -> str:
    is_bool = isinstance(param.ty, NormalParameter) and param.ty.ty.name == "Bool"
    pre = "0x997275b5 if " if is_bool else ""
    mid = f"_{param.name}" if is_computed(param.ty) else f"self.{sanitize_name(param.name)}"
    suf = " else 0xbc799737" if is_bool else ""
    return f"{pre}{mid}{suf}"


def generate_buffer_append(writer: SourceWriter, buffer: str, name: str, ty: Type) -> None:
    sanitized_name = sanitize_name(name)

    if is_trivial(NormalParameter(ty=ty, flag=None)):
        fmt = trivial_struct_fmt(NormalParameter(ty=ty, flag=None))
        if ty.name == "Bool":
            writer.write(
                f"{buffer} += struct.pack(f'<{fmt}', (0x997275b5 if {sanitized_name} else 0xbc799737))"
            )
        else:
            writer.write(f"{buffer} += struct.pack(f'<{fmt}', {sanitized_name})")
    elif ty.generic_ref or ty.name == "Object":
        writer.write(f"{buffer} += {sanitized_name}")  # assume previously-serialized
    elif ty.name == "string":
        writer.write(f"serialize_bytes_to({buffer}, {sanitized_name}.encode('utf-8'))")
    elif ty.name == "bytes":
        writer.write(f"serialize_bytes_to({buffer}, {sanitized_name})")
    elif ty.name == "int128":
        writer.write(f"{buffer} += {sanitized_name}.to_bytes(16)")
    elif ty.name == "int256":
        writer.write(f"{buffer} += {sanitized_name}.to_bytes(32)")
    elif ty.bare:
        writer.write(f"{sanitized_name}._write_to({buffer})")
    else:
        writer.write(f"{sanitized_name}._write_boxed_to({buffer})")


def generate_normal_param_write(
    writer: SourceWriter,
    tmp_names: Iterator[str],
    buffer: str,
    name: str,
    param: NormalParameter,
) -> None:
    if param.ty.name == "true":
        return  # special-cased "built-in"

    sanitized_name = sanitize_name(name)

    if param.flag:
        writer.write(f"if {sanitized_name} is not None:")
        writer.indent()

    if param.ty.generic_arg:
        if param.ty.name not in ("Vector", "vector"):
            raise ValueError("generic_arg deserialization for non-vectors is not supported")

        if param.ty.bare:
            writer.write(f"{buffer} += struct.pack('<i', len({sanitized_name}))")
        else:
            writer.write(f"{buffer} += struct.pack('<ii', 0x1cb5c415, len({sanitized_name}))")

        generic = NormalParameter(ty=param.ty.generic_arg, flag=None)
        if is_trivial(generic):
            fmt = trivial_struct_fmt(generic)
            if param.ty.generic_arg.name == "Bool":
                tmp = next(tmp_names)
                writer.write(
                    f"{buffer} += struct.pack(f'<{{len({sanitized_name})}}{fmt}', *(0x997275b5 if {tmp} else 0xbc799737 for {tmp} in {sanitized_name}))"
                )
            else:
                writer.write(
                    f"{buffer} += struct.pack(f'<{{len({sanitized_name})}}{fmt}', *{sanitized_name})"
                )
        else:
            tmp = next(tmp_names)
            writer.write(f"for {tmp} in {sanitized_name}:")
            writer.indent()
            generate_buffer_append(writer, buffer, tmp, param.ty.generic_arg)
            writer.dedent()
    else:
        generate_buffer_append(writer, buffer, f"{name}", param.ty)

    if param.flag:
        writer.dedent()


def generate_write(writer: SourceWriter, defn: Definition) -> None:
    tmp_names = gen_tmp_names()
    for trivial, iter in groupby(
        defn.params,
        key=lambda p: is_trivial(p.ty),
    ):
        if trivial:
            # As an optimization, struct.pack can handle more than one element at a time.
            group = list(iter)
            for param in group:
                if isinstance(param.ty, FlagsParameter):
                    flags = " | ".join(
                        (
                            f"({1 << p.ty.flag.index} if self.{sanitize_name(p.name)} else 0)"
                            if p.ty.ty.name == "true"
                            else f"(0 if self.{sanitize_name(p.name)} is None else {1 << p.ty.flag.index})"
                        )
                        for p in defn.params
                        if isinstance(p.ty, NormalParameter)
                        and p.ty.flag
                        and p.ty.flag.name == param.name
                    )
                    writer.write(f"_{param.name} = {flags or 0}")

            names = ", ".join(map(param_value_expr, group))
            fmt = "".join(trivial_struct_fmt(param.ty) for param in group)
            writer.write(f"buffer += struct.pack('<{fmt}', {names})")
        else:
            for param in iter:
                if not isinstance(param.ty, NormalParameter):
                    raise RuntimeError("FlagsParameter should be considered trivial")
                generate_normal_param_write(
                    writer, tmp_names, "buffer", f"self.{sanitize_name(param.name)}", param.ty
                )


def generate_function(writer: SourceWriter, defn: Definition) -> None:
    tmp_names = gen_tmp_names()
    serialized_cid = struct.pack("<I", defn.id)
    writer.write(f"_buffer = bytearray({serialized_cid!r})")
    for trivial, iter in groupby(
        defn.params,
        key=lambda p: is_trivial(p.ty),
    ):
        if trivial:
            # As an optimization, struct.pack can handle more than one element at a time.
            group = list(iter)
            for param in group:
                if isinstance(param.ty, FlagsParameter):
                    flags = " | ".join(
                        (
                            f"({1 << p.ty.flag.index} if {sanitize_name(p.name)} else 0)"
                            if p.ty.ty.name == "true"
                            else f"(0 if {sanitize_name(p.name)} is None else {1 << p.ty.flag.index})"
                        )
                        for p in defn.params
                        if isinstance(p.ty, NormalParameter)
                        and p.ty.flag
                        and p.ty.flag.name == param.name
                    )
                    writer.write(f"{param.name} = {flags or 0}")

            names = ", ".join(sanitize_name(p.name) for p in group)
            fmt = "".join(trivial_struct_fmt(param.ty) for param in group)
            writer.write(f"_buffer += struct.pack('<{fmt}', {names})")
        else:
            for param in iter:
                if not isinstance(param.ty, NormalParameter):
                    raise RuntimeError("FlagsParameter should be considered trivial")
                generate_normal_param_write(writer, tmp_names, "_buffer", param.name, param.ty)
    writer.write("return Request(b'' + _buffer)")
