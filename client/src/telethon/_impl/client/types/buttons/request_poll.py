from ....tl import types
from .button import Button


class RequestPoll(Button):
    """
    Keyboard button that will prompt the user to create a poll.

    :param text: See below.
    """

    def __init__(self, text: str, *, quiz: bool = False) -> None:
        super().__init__(text)
        self._raw = types.KeyboardButtonRequestPoll(text=text, quiz=quiz)
