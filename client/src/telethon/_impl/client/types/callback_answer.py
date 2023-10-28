from typing import Optional

from ...tl import abcs, types
from .meta import NoPublicConstructor


class CallbackAnswer(metaclass=NoPublicConstructor):
    """
    A bot's :class:`~telethon.types.buttons.Callback` :meth:`~telethon.events.ButtonCallback.answer`.
    """

    def __init__(self, raw: abcs.messages.BotCallbackAnswer) -> None:
        assert isinstance(raw, types.messages.BotCallbackAnswer)
        self._raw = raw

    @property
    def text(self) -> Optional[str]:
        """
        The answer's text, usually displayed as a toast.
        """
        return self._raw.message

    @property
    def url(self) -> Optional[str]:
        """
        The answer's URL.
        """
        return self._raw.url
