from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Optional

from ....tl import abcs, types
from .button import Button
from .callback import Callback
from .inline_button import InlineButton
from .request_geo_location import RequestGeoLocation
from .request_phone import RequestPhone
from .request_poll import RequestPoll
from .switch_inline import SwitchInline
from .text import Text
from .url import Url

if TYPE_CHECKING:
    from ..message import Message


def as_concrete_row(row: abcs.KeyboardButtonRow) -> types.KeyboardButtonRow:
    assert isinstance(row, types.KeyboardButtonRow)
    return row


def build_keyboard(
    btns: Optional[list[Button] | list[list[Button]]],
) -> Optional[abcs.ReplyMarkup]:
    # list[button] -> list[list[button]]
    # This does allow for "invalid" inputs (mixing lists and non-lists), but that's acceptable.
    buttons_lists_iter = (
        button if isinstance(button, list) else [button] for button in (btns or [])
    )
    # Remove empty rows (also making it easy to check if all-empty).
    buttons_lists = [bs for bs in buttons_lists_iter if bs]

    if not buttons_lists:
        return None

    rows: list[abcs.KeyboardButtonRow] = [
        types.KeyboardButtonRow(buttons=[btn._raw for btn in btns])
        for btns in buttons_lists
    ]

    # Guaranteed to have at least one, first one used to check if it's inline.
    # If the user mixed inline with non-inline, Telegram will complain.
    if isinstance(buttons_lists[0][0], InlineButton):
        return types.ReplyInlineMarkup(rows=rows)
    else:
        return types.ReplyKeyboardMarkup(
            resize=False,
            single_use=False,
            selective=False,
            persistent=False,
            rows=rows,
            placeholder=None,
        )


def create_button(message: Message, raw: abcs.KeyboardButton) -> Button:
    """
    Create a custom button from a Telegram button.

    Types with no friendly variant fallback to :class:`telethon.types.buttons.Button` or `telethon.types.buttons.Inline`.
    """
    cls = Button

    if isinstance(raw, types.KeyboardButtonCallback):
        cls = Callback
    elif isinstance(raw, types.KeyboardButtonRequestGeoLocation):
        cls = RequestGeoLocation
    elif isinstance(raw, types.KeyboardButtonRequestPhone):
        cls = RequestPhone
    elif isinstance(raw, types.KeyboardButtonRequestPoll):
        cls = RequestPoll
    elif isinstance(raw, types.KeyboardButtonSwitchInline):
        cls = SwitchInline
    elif isinstance(raw, types.KeyboardButton):
        cls = Text
    elif isinstance(raw, types.KeyboardButtonUrl):
        cls = Url
    elif isinstance(
        raw,
        (
            types.KeyboardButtonBuy,
            types.KeyboardButtonGame,
            types.KeyboardButtonUrlAuth,
            types.InputKeyboardButtonUrlAuth,
            types.KeyboardButtonWebView,
        ),
    ):
        cls = InlineButton
    elif isinstance(
        raw,
        (
            types.InputKeyboardButtonUserProfile,
            types.KeyboardButtonUserProfile,
            types.KeyboardButtonSimpleWebView,
            types.KeyboardButtonRequestPeer,
        ),
    ):
        cls = Button
    else:
        raise RuntimeError("unexpected case")

    instance = cls.__new__(cls)
    instance._msg = weakref.ref(message)
    instance._raw = raw
    return instance


__all__ = [
    "Button",
    "Callback",
    "InlineButton",
    "RequestGeoLocation",
    "RequestPhone",
    "RequestPoll",
    "SwitchInline",
    "Text",
    "Url",
]
