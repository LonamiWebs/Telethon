import abc

from .button import Button


class InlineButton(Button, abc.ABC):
    """
    Inline button base type.

    Inline buttons appear directly under a message (inline in the chat history).

    You cannot create a naked :class:`InlineButton` directly.
    Instead, it can be used to check whether a button is inline or not.

    Buttons that behave as a "custom key" and replace the user's virtual keyboard
    can be tested by checking that they are not inline.

    .. rubric:: Example

    .. code-block:: python

        from telethon.types import buttons

        is_inline_button = isinstance(button, buttons.Inline)
        is_keyboard_button = not isinstance(button, buttons.Inline)

    :param text: See below.
    """

    def __init__(self, text: str) -> None:
        if self.__class__ == InlineButton:
            raise TypeError(f"Can't instantiate abstract class {self.__class__.__name__}")
        else:
            super().__init__(text)
