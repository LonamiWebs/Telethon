from pathlib import Path
from typing import Set

from ..tl_parser import NormalParameter, ParsedTl
from .fakefs import FakeFs, SourceWriter
from .serde.common import (
    inner_type_fmt,
    is_computed,
    param_type_fmt,
    to_class_name,
    to_method_name,
)
from .serde.deserialization import (
    function_deserializer_fmt,
    generate_read,
    param_value_fmt,
)
from .serde.serialization import generate_function, generate_write


def generate_init(
    writer: SourceWriter, namespaces: Set[str], classes: Set[str]
) -> None:
    sorted_cls = list(sorted(classes))
    sorted_ns = list(sorted(namespaces))

    if sorted_cls:
        sorted_import = ", ".join(sorted_cls)
        writer.write(f"from ._nons import {sorted_import}")

    if sorted_ns:
        sorted_import = ", ".join(sorted_ns)
        writer.write(f"from . import {sorted_import}")

    if sorted_cls or sorted_ns:
        sorted_all = ", ".join(f"{ns!r}" for ns in sorted_cls + sorted_ns)
        writer.write(f"__all__ = [{sorted_all}]")


def generate(fs: FakeFs, tl: ParsedTl) -> None:
    generated_types = {
        "True",
        "Bool",
        "Object",
    }  # initial set is considered to be "compiler built-ins"

    ignored_types = {"true", "boolTrue", "boolFalse"}  # also "compiler built-ins"

    abc_namespaces = set()
    type_namespaces = set()
    function_namespaces = set()

    abc_class_names = set()
    type_class_names = set()
    function_def_names = set()
    generated_type_names = set()

    for typedef in tl.typedefs:
        if typedef.ty.full_name not in generated_types:
            if len(typedef.ty.namespace) >= 2:
                raise ValueError("nested abc-namespaces are not supported")
            elif len(typedef.ty.namespace) == 1:
                abc_namespaces.add(typedef.ty.namespace[0])
                abc_path = (Path("abcs") / typedef.ty.namespace[0]).with_suffix(".py")
            else:
                abc_class_names.add(to_class_name(typedef.ty.name))
                abc_path = Path("abcs/_nons.py")

            if abc_path not in fs:
                fs.write(abc_path, "from abc import ABCMeta\n")
                fs.write(abc_path, "from ..core import Serializable\n")

            fs.write(
                abc_path,
                f"class {to_class_name(typedef.ty.name)}(Serializable, metaclass=ABCMeta): pass\n",
            )
            generated_types.add(typedef.ty.full_name)

        if typedef.name in ignored_types:
            continue

        property_params = [p for p in typedef.params if not is_computed(p.ty)]

        if len(typedef.namespace) >= 2:
            raise ValueError("nested type-namespaces are not supported")
        elif len(typedef.namespace) == 1:
            type_namespaces.add(typedef.namespace[0])
            type_path = (Path("types") / typedef.namespace[0]).with_suffix(".py")
        else:
            type_class_names.add(to_class_name(typedef.name))
            type_path = Path("types/_nons.py")

        writer = fs.open(type_path)

        if type_path not in fs:
            writer.write("import struct")
            writer.write("from typing import List, Optional, Self, Sequence")
            writer.write("from .. import abcs")
            writer.write("from ..core import Reader, Serializable, serialize_bytes_to")

        ns = f"{typedef.namespace[0]}." if typedef.namespace else ""
        generated_type_names.add(f"{ns}{to_class_name(typedef.name)}")

        # class Type(BaseType)
        writer.write(
            f"class {to_class_name(typedef.name)}({inner_type_fmt(typedef.ty)}):"
        )

        #   __slots__ = ('params', ...)
        slots = " ".join(f"'{p.name}'," for p in property_params)
        writer.write(f"  __slots__ = ({slots})")

        #   def constructor_id()
        writer.write("  @classmethod")
        writer.write("  def constructor_id(_) -> int:")
        writer.write(f"    return {hex(typedef.id)}")

        #   def __init__()
        if property_params:
            params = "".join(
                f", {p.name}: {param_type_fmt(p.ty, immutable=False)}"
                for p in property_params
            )
            writer.write(f"  def __init__(_s, *{params}) -> None:")
            for p in property_params:
                writer.write(f"    _s.{p.name} = {p.name}")

        #   def _read_from()
        writer.write("  @classmethod")
        writer.write("  def _read_from(cls, reader: Reader) -> Self:")
        writer.indent(2)
        generate_read(writer, typedef)
        params = ", ".join(f"{p.name}={param_value_fmt(p)}" for p in property_params)
        writer.write(f"return cls({params})")
        writer.dedent(2)

        #   def _write_to()
        writer.write("  def _write_to(self, buffer: bytearray) -> None:")
        if typedef.params:
            writer.indent(2)
            generate_write(writer, typedef)
            writer.dedent(2)
        else:
            writer.write("    pass")

    for functiondef in tl.functiondefs:
        if len(functiondef.namespace) >= 2:
            raise ValueError("nested function-namespaces are not supported")
        elif len(functiondef.namespace) == 1:
            function_namespaces.add(functiondef.namespace[0])
            function_path = (Path("functions") / functiondef.namespace[0]).with_suffix(
                ".py"
            )
        else:
            function_def_names.add(to_method_name(functiondef.name))
            function_path = Path("functions/_nons.py")

        writer = fs.open(function_path)

        if function_path not in fs:
            writer.write("import struct")
            writer.write("from typing import List, Optional, Self, Sequence")
            writer.write("from .. import abcs")
            writer.write("from ..core import Request, serialize_bytes_to")

        #   def name(params, ...)
        required_params = [p for p in functiondef.params if not is_computed(p.ty)]
        params = "".join(
            f", {p.name}: {param_type_fmt(p.ty, immutable=True)}"
            for p in required_params
        )
        star = "*" if params else ""
        return_ty = param_type_fmt(
            NormalParameter(ty=functiondef.ty, flag=None), immutable=False
        )
        writer.write(
            f"def {to_method_name(functiondef.name)}({star}{params}) -> Request[{return_ty}]:"
        )
        writer.indent(2)
        generate_function(writer, functiondef)
        writer.dedent(2)

    generate_init(fs.open(Path("abcs/__init__.py")), abc_namespaces, abc_class_names)
    generate_init(fs.open(Path("types/__init__.py")), type_namespaces, type_class_names)
    generate_init(
        fs.open(Path("functions/__init__.py")), function_namespaces, function_def_names
    )

    writer = fs.open(Path("layer.py"))
    writer.write("from . import abcs, types")
    writer.write(
        "from .core import Serializable, Reader, deserialize_bool, deserialize_i32_list, deserialize_i64_list, deserialize_identity, single_deserializer, list_deserializer"
    )
    writer.write("from typing import cast, Tuple, Type")
    writer.write(f"LAYER = {tl.layer!r}")
    writer.write(
        "TYPE_MAPPING = {t.constructor_id(): t for t in cast(Tuple[Type[Serializable]], ("
    )
    for name in sorted(generated_type_names):
        writer.write(f"  types.{name},")
    writer.write("))}")
    writer.write("RESPONSE_MAPPING = {")
    for functiondef in tl.functiondefs:
        writer.write(
            f"  {hex(functiondef.id)}: {function_deserializer_fmt(functiondef)},"
        )
    writer.write("}")
    writer.write("__all__ = ['LAYER', 'TYPE_MAPPING', 'RESPONSE_MAPPING']")
