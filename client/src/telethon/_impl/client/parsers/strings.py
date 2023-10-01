import struct
from typing import List, Optional

from ...tl.abcs import MessageEntity


def add_surrogate(text: str) -> str:
    return "".join(
        # SMP -> Surrogate Pairs (Telegram offsets are calculated with these).
        # See https://en.wikipedia.org/wiki/Plane_(Unicode)#Overview for more.
        "".join(chr(y) for y in struct.unpack("<HH", x.encode("utf-16le")))
        if (0x10000 <= ord(x) <= 0x10FFFF)
        else x
        for x in text
    )


def del_surrogate(text: str) -> str:
    return text.encode("utf-16", "surrogatepass").decode("utf-16")


def within_surrogate(text: str, index: int, *, length: Optional[int] = None) -> bool:
    """
    :data:`True` if ``index`` is within a surrogate (before and after it, not at!).
    """
    if length is None:
        length = len(text)

    return (
        1 < index < len(text)  # in bounds
        and "\ud800" <= text[index - 1] <= "\udfff"  # previous is
        and "\ud800" <= text[index] <= "\udfff"  # current is
    )


def strip_text(text: str, entities: List[MessageEntity]) -> str:
    """
    Strips whitespace from the given text modifying the provided entities.

    This assumes that there are no overlapping entities, that their length
    is greater or equal to one, and that their length is not out of bounds.
    """
    if not entities:
        return text.strip()

    while text and text[-1].isspace():
        e = entities[-1]
        assert hasattr(e, "offset") and hasattr(e, "length")
        if e.offset + e.length == len(text):
            if e.length == 1:
                del entities[-1]
                if not entities:
                    return text.strip()
            else:
                e.length -= 1
        text = text[:-1]

    while text and text[0].isspace():
        for i in reversed(range(len(entities))):
            e = entities[i]
            assert hasattr(e, "offset") and hasattr(e, "length")
            if e.offset != 0:
                e.offset -= 1
                continue

            if e.length == 1:
                del entities[0]
                if not entities:
                    return text.lstrip()
            else:
                e.length -= 1

        text = text[1:]

    return text
