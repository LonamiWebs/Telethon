from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

from ....tl import abcs, types
from .button import Button
from .callback import Callback
from .inline_button import InlineButton
from .reply_markup import ReplyInlineMarkup, ReplyKeyboardMarkup
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
    "ReplyInlineMarkup",
    "ReplyKeyboardMarkup",
    "RequestGeoLocation",
    "RequestPhone",
    "RequestPoll",
    "SwitchInline",
    "Text",
    "Url",
]
