from ....tl import types
from .button import Button


class RequestPhone(Button):
    """
    Keyboard button that will prompt the user to share the contact with their phone number.

    :param text: See below.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._raw = types.KeyboardButtonRequestPhone(text=text)
