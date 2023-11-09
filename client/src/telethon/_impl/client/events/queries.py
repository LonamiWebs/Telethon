from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Self

from ...tl import abcs, functions, types
from ..types import Chat
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class ButtonCallback(Event):
    """
    Occurs when the user :meth:`~telethon.types.buttons.Callback.click`\ s a :class:`~telethon.types.buttons.Callback` button.

    Only bot accounts can receive this event, because only bots can send :class:`~telethon.types.buttons.Callback` buttons.
    """

    def __init__(
        self,
        client: Client,
        update: types.UpdateBotCallbackQuery,
        chat_map: Dict[int, Chat],
    ):
        self._client = client
        self._raw = update
        self._chat_map = chat_map

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateBotCallbackQuery) and update.data is not None:
            return cls._create(client, update, chat_map)
        else:
            return None

    @property
    def data(self) -> bytes:
        assert self._raw.data is not None
        return self._raw.data

    async def answer(
        self,
        text: Optional[str] = None,
        alert: bool = False,
        url: Optional[str] = None,
        cache_time: int = 0,
    ) -> None:
        """
        Answer the callback query.

        .. important::

            You must call this function for the loading circle to stop on the user's side.

        :param text:
            The text of the message to display to the user, usually as a toast.
        :param alert:
            If True, the answer will be shown as a pop-up alert that must be dismissed by the user.
        :param url:
            Url, to which user will be redirected upon pressing the button.
            It should be a link to the same bot with ?start=... parameter, or a link to the game.
        :param cache_time:
            Time in seconds to cache the answer on the client side,
            preventing repeated callback queries from being sent to the bot on subsequent button presses.
            A cache_time of 0 means each button press will send a callback query to the bot.
        """
        await self._client(
            functions.messages.set_bot_callback_answer(
                alert=alert,
                query_id=self._raw.query_id,
                message=text,
                url=url,
                cache_time=cache_time,
            )
        )


class InlineQuery(Event):
    """
    Occurs when users type ``@bot query`` in their chat box.

    Only bot accounts can receive this event.
    """

    def __init__(self, update: types.UpdateBotInlineQuery):
        self._raw = update

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateBotInlineQuery):
            return cls._create(update)
        else:
            return None
