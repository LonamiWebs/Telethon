from ._impl.tl.definition import Definition
from ._impl.tl.flag import Flag
from ._impl.tl.parameter import Parameter, TypeDefNotImplemented
from ._impl.tl.parameter_type import FlagsParameter, NormalParameter
from ._impl.tl.ty import Type
from ._impl.tl_iterator import FunctionDef, TypeDef
from ._impl.tl_iterator import iterate as parse_tl_file

__all__ = [
    "Definition",
    "Flag",
    "Parameter",
    "TypeDefNotImplemented",
    "FlagsParameter",
    "NormalParameter",
    "Type",
    "FunctionDef",
    "TypeDef",
    "parse_tl_file",
]
