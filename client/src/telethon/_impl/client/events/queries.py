from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Self

from ...tl import abcs, functions, types
from ..types import Chat, Message
from .event import Event
from ..types.chat import peer_id

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
    ) -> None:
        """
        Answer the callback query.

        .. important::

            You must call this function for the loading circle to stop on the user's side.

        :param text:
            The text of the message to display to the user, usually as a toast.

        :param alert:
            If :data:`True`, the message will be shown as a pop-up alert that must be dismissed by the user.
        """
        await self._client(
            functions.messages.set_bot_callback_answer(
                alert=alert,
                query_id=self._raw.query_id,
                message=text,
                url=None,
                cache_time=0,
            )
        )

    async def get_message(self) -> Optional[Message]:
        """
        Get the :class:`~telethon.types.Message` containing the button that was clicked.

        If the message is too old and is no longer accessible, :data:`None` is returned instead.
        """
        pid = peer_id(self._raw.peer)
        chat = self._chat_map.get(pid)
        if not chat:
            chat = await self._client._resolve_to_packed(pid)

        message = (await self._client.get_messages_with_ids(chat=chat, message_ids=[self._raw.msg_id]))[0]

        return message or None


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
