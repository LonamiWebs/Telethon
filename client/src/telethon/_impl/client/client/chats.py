from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional, Sequence

from ...session import PeerRef
from ...tl import abcs, functions, types
from ..types import (
    AdminRight,
    AsyncList,
    ChatLike,
    ChatRestriction,
    File,
    Participant,
    RecentAction,
    build_chat_map,
)
from .messages import SearchList

if TYPE_CHECKING:
    from .client import Client


class ParticipantList(AsyncList[Participant]):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._packed: Optional[PeerRef] = None
        self._offset = 0
        self._seen: set[int] = set()

    async def _fetch_next(self) -> None:
        if self._packed is None:
            self._packed = await self._client._resolve_to_packed(self._chat)

        if self._packed.is_channel():
            chanp = await self._client(
                functions.channels.get_participants(
                    channel=self._packed._to_input_channel(),
                    filter=types.ChannelParticipantsRecent(),
                    offset=self._offset,
                    limit=200,
                    hash=0,
                )
            )
            assert isinstance(chanp, types.channels.ChannelParticipants)

            chat_map = build_chat_map(self._client, chanp.users, chanp.chats)

            seen_count = len(self._seen)
            for p in chanp.participants:
                part = Participant._from_raw_channel(
                    self._client, self._packed, p, chat_map
                )
                pid = part._peer_id()
                if pid not in self._seen:
                    self._seen.add(pid)
                    self._buffer.append(part)

            self._total = chanp.count
            self._offset += len(chanp.participants)
            self._done = len(self._seen) == seen_count

        elif self._packed.is_chat():
            chatp = await self._client(
                functions.messages.get_full_chat(chat_id=self._packed.id)
            )
            assert isinstance(chatp, types.messages.ChatFull)
            assert isinstance(chatp.full_chat, types.ChatFull)

            chat_map = build_chat_map(self._client, chatp.users, chatp.chats)

            participants = chatp.full_chat.participants
            if isinstance(participants, types.ChatParticipantsForbidden):
                if participants.self_participant:
                    self._buffer.append(
                        Participant._from_raw_chat(
                            self._client,
                            self._packed,
                            participants.self_participant,
                            chat_map,
                        )
                    )
            elif isinstance(participants, types.ChatParticipants):
                self._buffer.extend(
                    Participant._from_raw_chat(self._client, self._packed, p, chat_map)
                    for p in participants.participants
                )

            self._total = len(self._buffer)
            self._done = True
        else:
            raise TypeError("can only get participants from channels and groups")


def get_participants(self: Client, chat: ChatLike) -> AsyncList[Participant]:
    return ParticipantList(self, chat)


class RecentActionList(AsyncList[RecentAction]):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._peer: Optional[types.InputChannel] = None
        self._offset = 0

    async def _fetch_next(self) -> None:
        if self._peer is None:
            self._peer = (
                await self._client._resolve_to_packed(self._chat)
            )._to_input_channel()

        result = await self._client(
            functions.channels.get_admin_log(
                channel=self._peer,
                q="",
                min_id=0,
                max_id=self._offset,
                limit=100,
                events_filter=None,
                admins=[],
            )
        )
        assert isinstance(result, types.channels.AdminLogResults)

        chat_map = build_chat_map(self._client, result.users, result.chats)
        self._buffer.extend(RecentAction._create(e, chat_map) for e in result.events)
        self._total += len(self._buffer)

        if self._buffer:
            self._offset = min(e.id for e in self._buffer)


def get_admin_log(self: Client, chat: ChatLike) -> AsyncList[RecentAction]:
    return RecentActionList(self, chat)


class ProfilePhotoList(AsyncList[File]):
    def __init__(
        self,
        client: Client,
        chat: ChatLike,
    ):
        super().__init__()
        self._client = client
        self._chat = chat
        self._peer: Optional[abcs.InputPeer] = None
        self._search_iter: Optional[SearchList] = None

    async def _fetch_next(self) -> None:
        if self._peer is None:
            self._peer = (
                await self._client._resolve_to_packed(self._chat)
            )._to_input_peer()

        if isinstance(self._peer, types.InputPeerUser):
            result = await self._client(
                functions.photos.get_user_photos(
                    user_id=types.InputUser(
                        user_id=self._peer.user_id, access_hash=self._peer.access_hash
                    ),
                    offset=0,
                    max_id=0,
                    limit=0,
                )
            )

            if isinstance(result, types.photos.Photos):
                photos = result.photos
                self._total = len(result.photos)
            elif isinstance(result, types.photos.PhotosSlice):
                photos = result.photos
                self._total = result.count
            else:
                raise RuntimeError("unexpected case")

            self._buffer.extend(
                filter(
                    None, (File._try_from_raw_photo(self._client, p) for p in photos)
                )
            )


def get_profile_photos(self: Client, chat: ChatLike) -> AsyncList[File]:
    return ProfilePhotoList(self, chat)


async def set_participant_admin_rights(
    self: Client, chat: ChatLike, user: ChatLike, rights: Sequence[AdminRight]
) -> None:
    packed = await self._resolve_to_packed(chat)
    participant = await self._resolve_to_packed(user)

    if packed.is_channel():
        admin_rights = AdminRight._set_to_raw(set(rights))
        await self(
            functions.channels.edit_admin(
                channel=packed._to_input_channel(),
                user_id=participant._to_input_user(),
                admin_rights=admin_rights,
                rank="",
            )
        )
    elif packed.is_chat():
        await self(
            functions.messages.edit_chat_admin(
                chat_id=packed.id,
                user_id=participant._to_input_user(),
                is_admin=bool(rights),
            )
        )
    else:
        raise TypeError(f"Cannot set admin rights in {packed.ty}")


async def set_participant_restrictions(
    self: Client,
    chat: ChatLike,
    user: ChatLike,
    restrictions: Sequence[ChatRestriction],
    *,
    until: Optional[datetime.datetime] = None,
) -> None:
    packed = await self._resolve_to_packed(chat)
    participant = await self._resolve_to_packed(user)
    if packed.is_channel():
        banned_rights = ChatRestriction._set_to_raw(
            set(restrictions),
            until_date=int(until.timestamp()) if until else 0x7FFFFFFF,
        )
        await self(
            functions.channels.edit_banned(
                channel=packed._to_input_channel(),
                participant=participant._to_input_peer(),
                banned_rights=banned_rights,
            )
        )
    elif packed.is_chat():
        if restrictions:
            await self(
                functions.messages.delete_chat_user(
                    revoke_history=ChatRestriction.VIEW_MESSAGES in restrictions,
                    chat_id=packed.id,
                    user_id=participant._to_input_user(),
                )
            )
    else:
        raise TypeError(f"Cannot set banned rights in {packed.ty}")


async def set_chat_default_restrictions(
    self: Client,
    chat: ChatLike,
    restrictions: Sequence[ChatRestriction],
    *,
    until: Optional[datetime.datetime] = None,
) -> None:
    peer = (await self._resolve_to_packed(chat))._to_input_peer()
    banned_rights = ChatRestriction._set_to_raw(
        set(restrictions), int(until.timestamp()) if until else 0x7FFFFFFF
    )
    await self(
        functions.messages.edit_chat_default_banned_rights(
            peer=peer, banned_rights=banned_rights
        )
    )
