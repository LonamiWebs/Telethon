from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Optional, TypeAlias

from ....tl import types

if TYPE_CHECKING:
    from ..message import Message


ButtonType: TypeAlias = (
    types.KeyboardButton
    | types.KeyboardButtonUrl
    | types.KeyboardButtonCallback
    | types.KeyboardButtonRequestPhone
    | types.KeyboardButtonRequestGeoLocation
    | types.KeyboardButtonSwitchInline
    | types.KeyboardButtonGame
    | types.KeyboardButtonBuy
    | types.KeyboardButtonUrlAuth
    | types.InputKeyboardButtonUrlAuth
    | types.KeyboardButtonRequestPoll
    | types.InputKeyboardButtonUserProfile
    | types.KeyboardButtonUserProfile
    | types.KeyboardButtonWebView
    | types.KeyboardButtonSimpleWebView
    | types.KeyboardButtonRequestPeer
)


class Button:
    """
    The button base type.

    All other :mod:`~telethon.types.buttons` inherit this class.

    You can only click buttons that have been received from Telegram.
    Attempting to click a button you created will fail with an error.

    Not all buttons can be clicked, and each button will do something different when clicked.
    The reason for this is that Telethon cannot interact with any user to complete certain tasks.
    Only straightforward actions can be performed automatically, such as sending a text message.

    To check if a button is clickable, use :func:`hasattr` on the ``'click'`` method.

    :param text: See below.
    """

    def __init__(self, text: str) -> None:
        if self.__class__ == Button:
            raise TypeError(
                f"Can't instantiate abstract class {self.__class__.__name__}"
            )

        self._raw: ButtonType = types.KeyboardButton(text=text)
        self._msg: Optional[weakref.ReferenceType[Message]] = None

    @property
    def text(self) -> str:
        """
        The button's text that is displayed to the user.
        """
        return self._raw.text

    @text.setter
    def text(self, value: str) -> None:
        self._raw.text = value

    def _message(self) -> Message:
        if self._msg and (message := self._msg()):
            return message
        else:
            raise ValueError("Buttons created by yourself cannot be clicked")
