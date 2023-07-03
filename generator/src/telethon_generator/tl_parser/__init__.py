from .._impl.tl_parser.tl.definition import Definition
from .._impl.tl_parser.tl.flag import Flag
from .._impl.tl_parser.tl.parameter import Parameter, TypeDefNotImplemented
from .._impl.tl_parser.tl.parameter_type import (
    BaseParameter,
    FlagsParameter,
    NormalParameter,
)
from .._impl.tl_parser.tl.ty import Type
from .._impl.tl_parser.tl_iterator import FunctionDef, TypeDef
from .._impl.tl_parser.tl_iterator import iterate as parse_tl_file

__all__ = [
    "Definition",
    "Flag",
    "Parameter",
    "TypeDefNotImplemented",
    "BaseParameter",
    "FlagsParameter",
    "NormalParameter",
    "Type",
    "FunctionDef",
    "TypeDef",
    "parse_tl_file",
]
