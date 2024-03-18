from typing import Optional

from ....tl import functions, types
from ..callback_answer import CallbackAnswer
from .inline_button import InlineButton


class Callback(InlineButton):
    """
    Inline button that will trigger a :class:`telethon.events.ButtonCallback` with the button's data.

    :param text: See below.
    :param data: See below.
    """

    def __init__(self, text: str, data: Optional[bytes] = None) -> None:
        super().__init__(text)
        self._raw = types.KeyboardButtonCallback(
            requires_password=False,
            text=text,
            data=data or text.encode("utf-8", errors="replace"),
        )

    @property
    def data(self) -> bytes:
        """
        The button's binary payload.

        This data will be received by :class:`telethon.events.ButtonCallback` when the button is pressed.
        """
        assert isinstance(self._raw, types.KeyboardButtonCallback)
        assert isinstance(self._raw.data, bytes)
        return self._raw.data

    @data.setter
    def data(self, value: bytes) -> None:
        assert isinstance(self._raw, types.KeyboardButtonCallback)
        self._raw.data = value

    async def click(self) -> Optional[CallbackAnswer]:
        """
        Click the button, sending the button's :attr:`data` to the bot.

        The bot will receive a :class:`~telethon.events.ButtonCallback` event
        which they must quickly :meth:`~telethon.events.ButtonCallback.answer`.

        The bot's answer will be returned, or :data:`None` if they don't answer in time.
        """
        message = self._message()

        return CallbackAnswer._create(
            await message._client(
                functions.messages.get_bot_callback_answer(
                    game=False,
                    peer=message.chat._ref._to_input_peer(),
                    msg_id=message.id,
                    data=self.data,
                    password=None,
                )
            )
        )
