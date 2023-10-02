from __future__ import annotations

import datetime
import sys
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple, TypeVar, Union

from ...session import PackedChat
from ...tl import abcs, functions, types
from ..parsers import parse_html_message, parse_markdown_message
from ..types import AsyncList, Chat, ChatLike, Message
from ..utils import build_chat_map, generate_random_id, peer_id

if TYPE_CHECKING:
    from .client import Client


def parse_message(
    *,
    text: Optional[Union[str, Message]],
    markdown: Optional[str],
    html: Optional[str],
    allow_empty: bool,
) -> Tuple[Union[str, Message], Optional[List[abcs.MessageEntity]]]:
    cnt = sum((text is not None, markdown is not None, html is not None))
    if cnt != 1:
        if cnt == 0 and allow_empty:
            return "", None
        raise ValueError("must specify exactly one of text, markdown or html")

    if text is not None:
        parsed, entities = text, None
    elif markdown is not None:
        parsed, entities = parse_markdown_message(markdown)
    elif html is not None:
        parsed, entities = parse_html_message(html)
    else:
        raise RuntimeError("unexpected case")

    return parsed, entities or None


async def send_message(
    self: Client,
    chat: ChatLike,
    text: Optional[Union[str, Message]] = None,
    *,
    markdown: Optional[str] = None,
    html: Optional[str] = None,
    link_preview: Optional[bool] = None,
    reply_to: Optional[int] = None,
) -> Message:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    message, entities = parse_message(
        text=text, markdown=markdown, html=html, allow_empty=False
    )
    random_id = generate_random_id()
    return self._build_message_map(
        await self(
            functions.messages.send_message(
                no_webpage=not link_preview,
                silent=False,
                background=False,
                clear_draft=False,
                noforwards=False,
                update_stickersets_order=False,
                peer=peer,
                reply_to=types.InputReplyToMessage(
                    reply_to_msg_id=reply_to, top_msg_id=None
                )
                if reply_to
                else None,
                message=message,
                random_id=random_id,
                reply_markup=None,
                entities=entities,
                schedule_date=None,
                send_as=None,
            )
            if isinstance(message, str)
            else functions.messages.send_message(
                no_webpage=not message.web_preview,
                silent=message.silent,
                background=False,
                clear_draft=False,
                noforwards=not message.can_forward,
                update_stickersets_order=False,
                peer=peer,
                reply_to=types.InputReplyToMessage(
                    reply_to_msg_id=message.replied_message_id, top_msg_id=None
                )
                if message.replied_message_id
                else None,
                message=message.text or "",
                random_id=random_id,
                reply_markup=getattr(message._raw, "reply_markup", None),
                entities=getattr(message._raw, "entities", None) or None,
                schedule_date=None,
                send_as=None,
            )
        ),
        peer,
    ).with_random_id(random_id)


async def edit_message(
    self: Client,
    chat: ChatLike,
    message_id: int,
    *,
    text: Optional[str] = None,
    markdown: Optional[str] = None,
    html: Optional[str] = None,
    link_preview: Optional[bool] = None,
) -> Message:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    message, entities = parse_message(
        text=text, markdown=markdown, html=html, allow_empty=False
    )
    assert isinstance(message, str)
    return self._build_message_map(
        await self(
            functions.messages.edit_message(
                no_webpage=not link_preview,
                peer=peer,
                id=message_id,
                message=message,
                media=None,
                reply_markup=None,
                entities=entities,
                schedule_date=None,
            )
        ),
        peer,
    ).with_id(message_id)


async def delete_messages(
    self: Client, chat: ChatLike, message_ids: List[int], *, revoke: bool = True
) -> int:
    packed_chat = await self._resolve_to_packed(chat)
    if packed_chat.is_channel():
        affected = await self(
            functions.channels.delete_messages(
                channel=packed_chat._to_input_channel(), id=message_ids
            )
        )
    else:
        affected = await self(
            functions.messages.delete_messages(revoke=revoke, id=message_ids)
        )
    assert isinstance(affected, types.messages.AffectedMessages)
    return affected.pts_count


async def forward_messages(
    self: Client, target: ChatLike, message_ids: List[int], source: ChatLike
) -> List[Message]:
    to_peer = (await self._resolve_to_packed(target))._to_input_peer()
    from_peer = (await self._resolve_to_packed(source))._to_input_peer()
    random_ids = [generate_random_id() for _ in message_ids]
    map = self._build_message_map(
        await self(
            functions.messages.forward_messages(
                silent=False,
                background=False,
                with_my_score=False,
                drop_author=False,
                drop_media_captions=False,
                noforwards=False,
                from_peer=from_peer,
                id=message_ids,
                random_id=random_ids,
                to_peer=to_peer,
                top_msg_id=None,
                schedule_date=None,
                send_as=None,
            )
        ),
        to_peer,
    )
    return [map.with_random_id(id) for id in random_ids]


class MessageList(AsyncList[Message]):
    def _extend_buffer(
        self, client: Client, messages: abcs.messages.Messages
    ) -> Dict[int, Chat]:
        if isinstance(messages, types.messages.Messages):
            chat_map = build_chat_map(messages.users, messages.chats)
            self._buffer.extend(
                Message._from_raw(client, m, chat_map) for m in messages.messages
            )
            self._total = len(messages.messages)
            self._done = True
            return chat_map
        elif isinstance(messages, types.messages.MessagesSlice):
            chat_map = build_chat_map(messages.users, messages.chats)
            self._buffer.extend(
                Message._from_raw(client, m, chat_map) for m in messages.messages
            )
            self._total = messages.count
            return chat_map
        elif isinstance(messages, types.messages.ChannelMessages):
            chat_map = build_chat_map(messages.users, messages.chats)
            self._buffer.extend(
                Message._from_raw(client, m, chat_map) for m in messages.messages
            )
            self._total = messages.count
            return chat_map
        elif isinstance(messages, types.messages.MessagesNotModified):
            self._total = messages.count
            return {}
        else:
            raise RuntimeError("unexpected case")

    def _last_non_empty_message(
        self,
    ) -> Union[types.Message, types.MessageService, types.MessageEmpty]:
        return next(
            (
                m._raw
                for m in reversed(self._buffer)
                if not isinstance(m._raw, types.MessageEmpty)
            ),
            types.MessageEmpty(id=0, peer_id=None),
        )


class HistoryList(MessageList):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
        limit: int,
        *,
        offset_id: int,
        offset_date: int,
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._peer: Optional[abcs.InputPeer] = None
        self._limit = limit
        self._offset_id = offset_id
        self._offset_date = offset_date

        self._done = limit <= 0

    async def _fetch_next(self) -> None:
        if self._peer is None:
            self._peer = (
                await self._client._resolve_to_packed(self._chat)
            )._to_input_peer()

        result = await self._client(
            functions.messages.get_history(
                peer=self._peer,
                offset_id=self._offset_id,
                offset_date=self._offset_date,
                add_offset=0,
                limit=min(max(self._limit, 1), 100),
                max_id=0,
                min_id=0,
                hash=0,
            )
        )

        self._extend_buffer(self._client, result)
        self._limit -= len(self._buffer)
        self._done |= not self._limit
        if self._buffer and not self._done:
            last = self._last_non_empty_message()
            self._offset_id = self._buffer[-1].id
            if (date := getattr(last, "date", None)) is not None:
                self._offset_date = date


def get_messages(
    self: Client,
    chat: ChatLike,
    limit: Optional[int] = None,
    *,
    offset_id: Optional[int] = None,
    offset_date: Optional[datetime.datetime] = None,
) -> AsyncList[Message]:
    return HistoryList(
        self,
        chat,
        sys.maxsize if limit is None else limit,
        offset_id=offset_id or 0,
        offset_date=int(offset_date.timestamp()) if offset_date is not None else 0,
    )


class CherryPickedList(MessageList):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
        ids: List[int],
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._packed: Optional[PackedChat] = None
        self._ids: List[abcs.InputMessage] = [types.InputMessageId(id=id) for id in ids]

    async def _fetch_next(self) -> None:
        if not self._ids:
            return
        if self._packed is None:
            self._packed = await self._client._resolve_to_packed(self._chat)

        if self._packed.is_channel():
            result = await self._client(
                functions.channels.get_messages(
                    channel=self._packed._to_input_channel(), id=self._ids[:100]
                )
            )
        else:
            result = await self._client(
                functions.messages.get_messages(id=self._ids[:100])
            )

        self._extend_buffer(self._client, result)
        self._ids = self._ids[100:]


def get_messages_with_ids(
    self: Client,
    chat: ChatLike,
    message_ids: List[int],
) -> AsyncList[Message]:
    return CherryPickedList(self, chat, message_ids)


class SearchList(MessageList):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
        limit: int,
        *,
        query: str,
        offset_id: int,
        offset_date: int,
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._peer: Optional[abcs.InputPeer] = None
        self._limit = limit
        self._query = query
        self._filter = types.InputMessagesFilterEmpty()
        self._offset_id = offset_id
        self._offset_date = offset_date

    async def _fetch_next(self) -> None:
        if self._peer is None:
            self._peer = (
                await self._client._resolve_to_packed(self._chat)
            )._to_input_peer()

        result = await self._client(
            functions.messages.search(
                peer=self._peer,
                q=self._query,
                from_id=None,
                top_msg_id=None,
                filter=self._filter,
                min_date=0,
                max_date=self._offset_date,
                offset_id=self._offset_id,
                add_offset=0,
                limit=min(max(self._limit, 1), 100),
                max_id=0,
                min_id=0,
                hash=0,
            )
        )

        self._extend_buffer(self._client, result)
        self._limit -= len(self._buffer)
        if self._buffer:
            last = self._last_non_empty_message()
            self._offset_id = self._buffer[-1].id
            if (date := getattr(last, "date", None)) is not None:
                self._offset_date = date


def search_messages(
    self: Client,
    chat: ChatLike,
    limit: Optional[int] = None,
    *,
    query: Optional[str] = None,
    offset_id: Optional[int] = None,
    offset_date: Optional[datetime.datetime] = None,
) -> AsyncList[Message]:
    return SearchList(
        self,
        chat,
        sys.maxsize if limit is None else limit,
        query=query or "",
        offset_id=offset_id or 0,
        offset_date=int(offset_date.timestamp()) if offset_date is not None else 0,
    )


class GlobalSearchList(MessageList):
    def __init__(
        self,
        client: Client,
        limit: int,
        *,
        query: str,
        offset_id: int,
        offset_date: int,
    ):
        super().__init__()
        self._client = client
        self._limit = limit
        self._query = query
        self._offset_id = offset_id
        self._offset_date = offset_date
        self._offset_rate = 0
        self._offset_peer: abcs.InputPeer = types.InputPeerEmpty()

    async def _fetch_next(self) -> None:
        result = await self._client(
            functions.messages.search_global(
                folder_id=None,
                q=self._query,
                filter=types.InputMessagesFilterEmpty(),
                min_date=0,
                max_date=self._offset_date,
                offset_rate=self._offset_rate,
                offset_peer=self._offset_peer,
                offset_id=self._offset_id,
                limit=min(max(self._limit, 1), 100),
            )
        )

        chat_map = self._extend_buffer(self._client, result)
        self._limit -= len(self._buffer)
        if self._buffer:
            last = self._last_non_empty_message()

            self._offset_id = self._buffer[-1].id
            if (date := getattr(last, "date", None)) is not None:
                self._offset_date = date
            if isinstance(result, types.messages.MessagesSlice):
                self._offset_rate = result.next_rate or 0

            self._offset_peer = types.InputPeerEmpty()
            if last.peer_id and (chat := chat_map.get(peer_id(last.peer_id))):
                if packed := chat.pack():
                    self._offset_peer = packed._to_input_peer()


def search_all_messages(
    self: Client,
    limit: Optional[int] = None,
    *,
    query: Optional[str] = None,
    offset_id: Optional[int] = None,
    offset_date: Optional[datetime.datetime] = None,
) -> AsyncList[Message]:
    return GlobalSearchList(
        self,
        sys.maxsize if limit is None else limit,
        query=query or "",
        offset_id=offset_id or 0,
        offset_date=int(offset_date.timestamp()) if offset_date is not None else 0,
    )


async def pin_message(self: Client, chat: ChatLike, message_id: int) -> Message:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    return self._build_message_map(
        await self(
            functions.messages.update_pinned_message(
                silent=True, unpin=False, pm_oneside=False, peer=peer, id=message_id
            )
        ),
        peer,
    ).get_single()


async def unpin_message(
    self: Client, chat: ChatLike, message_id: Union[int, Literal["all"]]
) -> None:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    if message_id == "all":
        await self(
            functions.messages.unpin_all_messages(
                peer=peer,
                top_msg_id=None,
            )
        )
    else:
        await self(
            functions.messages.update_pinned_message(
                silent=True, unpin=True, pm_oneside=False, peer=peer, id=message_id
            )
        )


class MessageMap:
    __slots__ = ("_client", "_peer", "_random_id_to_id", "_id_to_message")

    def __init__(
        self,
        client: Client,
        peer: Optional[abcs.InputPeer],
        random_id_to_id: Dict[int, int],
        id_to_message: Dict[int, Message],
    ) -> None:
        self._client = client
        self._peer = peer
        self._random_id_to_id = random_id_to_id
        self._id_to_message = id_to_message

    def with_random_id(self, random_id: int) -> Message:
        id = self._random_id_to_id.get(random_id)
        return self.with_id(id) if id is not None else self._empty()

    def with_id(self, id: int) -> Message:
        message = self._id_to_message.get(id)
        return message if message is not None else self._empty(id)

    def get_single(self) -> Message:
        if len(self._id_to_message) == 1:
            for message in self._id_to_message.values():
                return message
        return self._empty()

    def _empty(self, id: int = 0) -> Message:
        return Message._from_raw(
            self._client,
            types.MessageEmpty(id=id, peer_id=self._client._input_to_peer(self._peer)),
            {},
        )


def build_message_map(
    client: Client,
    result: abcs.Updates,
    peer: Optional[abcs.InputPeer],
) -> MessageMap:
    if isinstance(result, (types.Updates, types.UpdatesCombined)):
        updates = result.updates
        chat_map = build_chat_map(result.users, result.chats)
    elif isinstance(result, types.UpdateShort):
        updates = [result.update]
        chat_map = {}
    else:
        return MessageMap(client, peer, {}, {})

    random_id_to_id = {}
    id_to_message = {}
    for update in updates:
        if isinstance(update, types.UpdateMessageId):
            random_id_to_id[update.random_id] = update.id

        elif isinstance(
            update,
            (
                types.UpdateNewChannelMessage,
                types.UpdateNewMessage,
                types.UpdateEditMessage,
                types.UpdateEditChannelMessage,
                types.UpdateNewScheduledMessage,
            ),
        ):
            msg = Message._from_raw(client, update.message, chat_map)
            id_to_message[msg.id] = msg

    return MessageMap(
        client,
        peer,
        random_id_to_id,
        id_to_message,
    )
