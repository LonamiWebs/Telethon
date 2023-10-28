from __future__ import annotations

from typing import TYPE_CHECKING

from .button import Button

if TYPE_CHECKING:
    from ..message import Message


class Text(Button):
    """
    This is the most basic keyboard button and only has :attr:`text`.

    Note that it is not possible to distinguish between a :meth:`click` to this button being and the user typing the text themselves.

    :param text: See below.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)

    @property
    def text(self) -> str:
        """
        The button's text that is both displayed to the user and will be sent on :meth:`click`.
        """
        return self._raw.text

    @text.setter
    def text(self, value: str) -> None:
        self._raw.text = value

    async def click(self) -> Message:
        """
        Click the button, sending a message to the chat as-if the user typed and sent the text themselves.
        """
        return await self._message().respond(self._raw.text)
