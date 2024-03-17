import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .tl import Definition
from .tl_iterator import FunctionDef, TypeDef, iterate


@dataclass
class ParsedTl:
    layer: Optional[int]
    typedefs: list[Definition]
    functiondefs: list[Definition]


def load_tl_file(path: str | Path) -> ParsedTl:
    typedefs: list[TypeDef] = []
    functiondefs: list[FunctionDef] = []
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
        else:
            functiondefs.append(definition)

    return ParsedTl(
        layer=layer, typedefs=list(typedefs), functiondefs=list(functiondefs)
    )
