from ....tl import types
from .button import Button


class RequestGeoLocation(Button):
    """
    Keyboard button that will prompt the user to share the geo point with their current location.

    :param text: See below.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._raw = types.KeyboardButtonRequestGeoLocation(text=text)
