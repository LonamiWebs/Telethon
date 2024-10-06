from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from ...session import PeerRef
from ...tl import functions, types
from ..types import (
    AsyncList,
    Dialog,
    Draft,
    Peer,
    build_chat_map,
    build_msg_map,
    parse_message,
)

if TYPE_CHECKING:
    from .client import Client


class DialogList(AsyncList[Dialog]):
    def __init__(self, client: Client) -> None:
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

        chat_map = build_chat_map(self._client, result.users, result.chats)
        msg_map = build_msg_map(self._client, result.messages, chat_map)

        self._buffer.extend(
            Dialog._from_raw(self._client, d, chat_map, msg_map) for d in result.dialogs
        )


def get_dialogs(self: Client) -> AsyncList[Dialog]:
    return DialogList(self)


async def delete_dialog(self: Client, dialog: Peer | PeerRef, /) -> None:
    peer = dialog._ref
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


class DraftList(AsyncList[Draft]):
    def __init__(self, client: Client) -> None:
        super().__init__()
        self._client = client
        self._offset = 0

    async def _fetch_next(self) -> None:
        result = await self._client(functions.messages.get_all_drafts())
        assert isinstance(result, types.Updates)

        chat_map = build_chat_map(self._client, result.users, result.chats)

        self._buffer.extend(
            Draft._from_raw_update(self._client, u, chat_map)
            for u in result.updates
            if isinstance(u, types.UpdateDraftMessage)
        )

        self._total = len(result.updates)
        self._done = True


def get_drafts(self: Client) -> AsyncList[Draft]:
    return DraftList(self)


async def edit_draft(
    self: Client,
    peer: Peer | PeerRef,
    /,
    text: Optional[str] = None,
    *,
    markdown: Optional[str] = None,
    html: Optional[str] = None,
    link_preview: bool = False,
    reply_to: Optional[int] = None,
) -> Draft:
    peer = peer._ref
    message, entities = parse_message(
        text=text, markdown=markdown, html=html, allow_empty=False
    )

    result = await self(
        functions.messages.save_draft(
            no_webpage=not link_preview,
            reply_to_msg_id=reply_to,
            top_msg_id=None,
            peer=peer._to_input_peer(),
            message=message,
            entities=entities,
        )
    )
    assert result

    return Draft._from_raw(
        client=self,
        peer=peer._to_peer(),
        top_msg_id=0,
        draft=types.DraftMessage(
            no_webpage=not link_preview,
            reply_to_msg_id=reply_to,
            message=message,
            entities=entities,
            date=int(time.time()),
        ),
        chat_map={},
    )
