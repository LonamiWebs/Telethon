from __future__ import annotations

from typing import TYPE_CHECKING

from ...tl import abcs, functions, types
from ..types import AsyncList, ChatLike, Dialog, User
from ..utils import build_chat_map

if TYPE_CHECKING:
    from .client import Client


class DialogList(AsyncList[Dialog]):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client
        self._offset = 0

    async def _fetch_next(self) -> None:
        result = await self._client(
            functions.messages.get_dialogs(
                exclude_pinned=False,
                folder_id=None,
                offset_date=0,
                offset_id=0,
                offset_peer=types.InputPeerEmpty(),
                limit=0,
                hash=0,
            )
        )

        if isinstance(result, types.messages.Dialogs):
            self._total = len(result.dialogs)
            self._done = True
        elif isinstance(result, types.messages.DialogsSlice):
            self._total = result.count
        else:
            raise RuntimeError("unexpected case")

        assert isinstance(result, (types.messages.Dialogs, types.messages.DialogsSlice))

        chat_map = build_chat_map(result.users, result.chats)

        self._buffer.extend(Dialog._from_raw(d, chat_map) for d in result.dialogs)


def get_dialogs(self: Client) -> AsyncList[Dialog]:
    return DialogList(self)


async def delete_dialog(self: Client, chat: ChatLike) -> None:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    if isinstance(peer, types.InputPeerChannel):
        await self(
            functions.channels.leave_channel(
                channel=types.InputChannel(
                    channel_id=peer.channel_id,
                    access_hash=peer.access_hash,
                )
            )
        )
    elif isinstance(peer, types.InputPeerChat):
        await self(
            functions.messages.delete_chat_user(
                revoke_history=False,
                chat_id=peer.chat_id,
                user_id=types.InputUserSelf(),
            )
        )
    elif isinstance(peer, types.InputPeerUser):
        await self(
            functions.messages.delete_history(
                just_clear=False,
                revoke=False,
                peer=peer,
                max_id=0,
                min_date=None,
                max_date=None,
            )
        )
