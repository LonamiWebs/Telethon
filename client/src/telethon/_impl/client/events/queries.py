from __future__ import annotations

import struct
import typing
from typing import TYPE_CHECKING, Dict, Optional, Self, Union

from ...tl import abcs, functions, types
from ..types import Chat, Message, Channel
from .event import Event
from ..types.chat import peer_id
from ..client.messages import CherryPickedList

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
        update: Union[types.UpdateBotCallbackQuery, types.UpdateInlineBotCallbackQuery],
        chat_map: Dict[int, Chat],
    ):
        self._client = client
        self._raw = update
        self._chat_map = chat_map

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if (
            isinstance(
                update,
                (types.UpdateBotCallbackQuery, types.UpdateInlineBotCallbackQuery),
            )
            and update.data is not None
        ):
            return cls._create(client, update, chat_map)
        else:
            return None

    @property
    def data(self) -> bytes:
        assert self._raw.data is not None
        return self._raw.data

    @property
    def via_inline(self) -> bool:
        """
        Whether the button was clicked in an inline message.

        If it was, most likely bot is not in chat, and the :meth:`chat` property will return :data:`None`,
        same for :meth:`get_message` method, however editing the message, using :meth:`message_id` property
        and :meth:`answer` method will work.
        """
        return isinstance(self._raw, types.UpdateInlineBotCallbackQuery)

    @property
    def message_id(self) -> typing.Union[int, abcs.InputBotInlineMessageId]:
        """
        The ID of the message containing the button that was clicked.
        
        If the message is inline, :class:`abcs.InputBotInlineMessageId` will be returned.
        You can use it in :meth:`~telethon._tl.functions.messages.edit_inline_bot_message` to edit the message.

        Else, usual message ID will be returned.
        """
        return self._raw.msg_id

    @property
    def chat(self) -> Optional[Chat]:
        """
        The :term:`chat` where the button was clicked.

        This will be :data:`None` if the message with the button was sent from a user's inline query, except in channel.
        """
        if isinstance(self._raw, types.UpdateInlineBotCallbackQuery):
            owner_id = None
            if isinstance(self._raw.msg_id, types.InputBotInlineMessageId):
                _, owner_id = struct.unpack("<ii", struct.pack("<q", self._raw.msg_id.id))
            elif isinstance(self._raw.msg_id, types.InputBotInlineMessageId64):
                _ = self._raw.msg_id.id
                owner_id = self._raw.msg_id.owner_id

            if owner_id is None:
                return None

            if owner_id > 0:
                # We can't know if it's really a chat with user, or an ID of the user who issued the inline query.
                # So it's better to return None, then to return wrong chat.
                return None

            owner_id = -owner_id

            access_hash = 0
            packed = self.client._chat_hashes.get(owner_id)
            if packed:
                access_hash = packed.access_hash

            return Channel._from_raw(
                types.ChannelForbidden(
                    broadcast=True,
                    megagroup=False,
                    id=owner_id,
                    access_hash=access_hash,
                    title="",
                    until_date=None,
                )
            )
        return self._chat_map.get(peer_id(self._raw.peer))

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

        If the message is inline, or too old and is no longer accessible, :data:`None` is returned instead.
        """
        chat = None

        if isinstance(self._raw, types.UpdateInlineBotCallbackQuery):
            # for that type of update, the msg_id and owner_id are present, however bot is not guaranteed
            # to have "access" to the owner_id.
            if isinstance(self._raw.msg_id, types.InputBotInlineMessageId):
                # telegram used to pack msg_id and peer_id into InputBotInlineMessageId.id
                # I assume this is for the chats with IDs, fitting into 32-bit integer.
                msg_id, owner_id = struct.unpack(
                    "<ii", struct.pack("<q", self._raw.msg_id.id)
                )
            elif isinstance(self._raw.msg_id, types.InputBotInlineMessageId64):
                msg_id = self._raw.msg_id.id
                owner_id = self._raw.msg_id.owner_id
            else:
                return None

            msg = types.InputMessageCallbackQuery(
                id=msg_id, query_id=self._raw.query_id
            )
            if owner_id < 0:
                # that means update's owner_id actually is the peer (channel), where the button was clicked.
                # if it was positive, it'd be the user who issued the inline query.
                try:
                    chat = await self._client._resolve_to_packed(-owner_id)
                except ValueError:
                    pass
        else:
            pid = peer_id(self._raw.peer)
            msg = types.InputMessageCallbackQuery(
                id=self._raw.msg_id, query_id=self._raw.query_id
            )

            chat = self._chat_map.get(pid)
            if not chat:
                chat = await self._client._resolve_to_packed(pid)

        if chat:
            lst = CherryPickedList(self._client, chat, [])
            lst._ids.append(msg)

            res = await lst
            if res:
                return res[0] or None

        res = await self._client(
            functions.messages.get_messages(
                id=[msg],
            )
        )
        return res.messages[0] if res.messages else None


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
