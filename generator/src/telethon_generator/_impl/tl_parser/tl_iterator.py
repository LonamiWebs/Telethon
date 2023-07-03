from typing import Iterator, Type

from .tl.definition import Definition
from .utils import remove_tl_comments

DEFINITION_SEP = ";"
CATEGORY_MARKER = "---"
FUNCTIONS_SEP = f"{CATEGORY_MARKER}functions---"
TYPES_SEP = f"{CATEGORY_MARKER}types---"


class TypeDef(Definition):
    pass


class FunctionDef(Definition):
    pass


def iterate(contents: str) -> Iterator[TypeDef | FunctionDef | Exception]:
    contents = remove_tl_comments(contents)
    index = 0
    cls: Type[TypeDef] | Type[FunctionDef] = TypeDef
    while index < len(contents):
        if (end := contents.find(DEFINITION_SEP, index)) == -1:
            end = len(contents)

        definition = contents[index:end].strip()
        index = end + len(DEFINITION_SEP)

        if not definition:
            continue

        if definition.startswith(CATEGORY_MARKER):
            if definition.startswith(FUNCTIONS_SEP):
                cls = FunctionDef
                definition = definition[len(FUNCTIONS_SEP) :].strip()
            elif definition.startswith(TYPES_SEP):
                cls = TypeDef
                definition = definition[len(FUNCTIONS_SEP) :].strip()
            else:
                raise ValueError("bad separator")

        try:
            yield cls.from_str(definition)
        except Exception as e:
            yield e
