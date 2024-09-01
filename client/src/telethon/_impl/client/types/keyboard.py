from typing import Optional, TypeAlias, TypeVar

from ...tl import abcs, types
from .buttons import Button, InlineButton

AnyButton = TypeVar("AnyButton", bound=Button)
AnyInlineButton = TypeVar("AnyInlineButton", bound=InlineButton)


def _build_keyboard_rows(
    btns: list[AnyButton] | list[list[AnyButton]],
) -> list[abcs.KeyboardButtonRow]:
    # list[button] -> list[list[button]]
    # This does allow for "invalid" inputs (mixing lists and non-lists), but that's acceptable.
    buttons_lists_iter = [
        button if isinstance(button, list) else [button] for button in (btns or [])
    ]
    # Remove empty rows (also making it easy to check if all-empty).
    buttons_lists = [bs for bs in buttons_lists_iter if bs]

    return [
        types.KeyboardButtonRow(buttons=[btn._raw for btn in btns])
        for btns in buttons_lists
    ]


class Keyboard:
    __slots__ = ("_raw",)

    def __init__(
        self,
        buttons: list[AnyButton] | list[list[AnyButton]],
        resize: bool,
        single_use: bool,
        selective: bool,
        persistent: bool,
        placeholder: Optional[str],
    ) -> None:
        self._raw = types.ReplyKeyboardMarkup(
            resize=resize,
            single_use=single_use,
            selective=selective,
            persistent=persistent,
            rows=_build_keyboard_rows(buttons),
            placeholder=placeholder,
        )


class InlineKeyboard:
    __slots__ = ("_raw",)

    def __init__(
        self, buttons: list[AnyInlineButton] | list[list[AnyInlineButton]]
    ) -> None:
        self._raw = types.ReplyInlineMarkup(rows=_build_keyboard_rows(buttons))


KeyboardType: TypeAlias = Keyboard | InlineKeyboard
