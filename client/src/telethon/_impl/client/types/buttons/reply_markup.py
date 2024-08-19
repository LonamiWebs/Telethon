from typing import Optional, TypeAlias

from ....tl import abcs, types
from .button import Button


def build_keyboard_rows(
    btns: list[Button] | list[list[Button]],
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


class ReplyKeyboardMarkup:
    __slots__ = (
        "_btns",
        "resize",
        "single_use",
        "selective",
        "persistent",
        "placeholder",
    )

    def __init__(
        self,
        btns: list[Button] | list[list[Button]],
        resize: bool,
        single_use: bool,
        selective: bool,
        persistent: bool,
        placeholder: Optional[str],
    ) -> None:
        self._btns = build_keyboard_rows(btns)
        self.resize = resize
        self.single_use = single_use
        self.selective = selective
        self.persistent = persistent
        self.placeholder = placeholder

    def build(self) -> abcs.ReplyMarkup:
        return types.ReplyKeyboardMarkup(
            resize=self.resize,
            single_use=self.single_use,
            selective=self.selective,
            persistent=self.persistent,
            rows=self._btns,
            placeholder=self.placeholder,
        )


class ReplyInlineMarkup:
    __slots__ = ("_btns",)

    def __init__(self, btns: list[Button] | list[list[Button]]) -> None:
        self._btns = build_keyboard_rows(btns)

    def build(self) -> abcs.ReplyMarkup:
        return types.ReplyInlineMarkup(rows=self._btns)


ReplyMarkupType: TypeAlias = ReplyKeyboardMarkup | ReplyInlineMarkup
