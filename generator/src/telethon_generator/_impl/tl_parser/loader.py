import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from .tl import Definition
from .tl_iterator import FunctionDef, TypeDef, iterate


@dataclass
class ParsedTl:
    layer: Optional[int]
    typedefs: List[Definition]
    functiondefs: List[Definition]


def load_tl_file(path: Union[str, Path]) -> ParsedTl:
    typedefs, functiondefs = [], []
    with open(path, "r", encoding="utf-8") as fd:
        contents = fd.read()

    if m := re.search(r"//\s*LAYER\s+(\d+)", contents):
        layer = int(m[1])
    else:
        layer = None

    for definition in iterate(contents):
        if isinstance(definition, Exception):
            # generic types (such as vector) is known to not be implemented
            if definition.args[0] != "not implemented":
                raise
        elif isinstance(definition, TypeDef):
            typedefs.append(definition)
        elif isinstance(definition, FunctionDef):
            functiondefs.append(definition)
        else:
            raise TypeError(f"unexpected type: {type(definition)}")

    return ParsedTl(
        layer=layer, typedefs=list(typedefs), functiondefs=list(functiondefs)
    )
