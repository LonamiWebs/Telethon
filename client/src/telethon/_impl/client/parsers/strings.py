import struct
from typing import Optional


def add_surrogate(text: str) -> str:
    return "".join(
        # SMP -> Surrogate Pairs (Telegram offsets are calculated with these).
        # See https://en.wikipedia.org/wiki/Plane_(Unicode)#Overview for more.
        ("".join(chr(y) for y in struct.unpack("<HH", x.encode("utf-16le"))) if (0x10000 <= ord(x) <= 0x10FFFF) else x)
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
