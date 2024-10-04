from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional, Sequence

from ...session import ChannelRef, GroupRef, PeerRef, UserRef
from ...tl import functions, types
from ..types import (
    AdminRight,
    AsyncList,
    Channel,
    ChatRestriction,
    File,
    Group,
    Participant,
    Peer,
    RecentAction,
    User,
    build_chat_map,
)
from .messages import SearchList

if TYPE_CHECKING:
    from .client import Client


class ParticipantList(AsyncList[Participant]):
    def __init__(
        self,
        client: Client,
        peer: ChannelRef | GroupRef,
    ):
        super().__init__()
        self._client = client
        self._peer = peer
        self._offset = 0
        self._seen: set[int] = set()

    async def _fetch_next(self) -> None:
        if isinstance(self._peer, ChannelRef):
            chanp = await self._client(
                functions.channels.get_participants(
                    channel=self._peer._to_input_channel(),
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
                part = Participant._from_raw_channel(self._client, self._peer, p, chat_map)
                pid = part._peer_id()
                if pid not in self._seen:
                    self._seen.add(pid)
                    self._buffer.append(part)

            self._total = chanp.count
            self._offset += len(chanp.participants)
            self._done = len(self._seen) == seen_count

        else:
            chatp = await self._client(functions.messages.get_full_chat(chat_id=self._peer._to_input_chat()))
            assert isinstance(chatp, types.messages.ChatFull)
            assert isinstance(chatp.full_chat, types.ChatFull)

            chat_map = build_chat_map(self._client, chatp.users, chatp.chats)

            participants = chatp.full_chat.participants
            if isinstance(participants, types.ChatParticipantsForbidden):
                if participants.self_participant:
                    self._buffer.append(
                        Participant._from_raw_chat(
                            self._client,
                            self._peer,
                            participants.self_participant,
                            chat_map,
                        )
                    )
            elif isinstance(participants, types.ChatParticipants):
                self._buffer.extend(
                    Participant._from_raw_chat(self._client, self._peer, p, chat_map) for p in participants.participants
                )

            self._total = len(self._buffer)
            self._done = True


def get_participants(self: Client, chat: Group | Channel | GroupRef | ChannelRef, /) -> AsyncList[Participant]:
    return ParticipantList(self, chat._ref)


class RecentActionList(AsyncList[RecentAction]):
    def __init__(
        self,
        client: Client,
        peer: ChannelRef | GroupRef,
    ):
        super().__init__()
        self._client = client
        self._peer = peer
        self._offset = 0

    async def _fetch_next(self) -> None:
        if not isinstance(self._peer, ChannelRef):
            return  # small group chats have no recent actions

        result = await self._client(
            functions.channels.get_admin_log(
                channel=self._peer._to_input_channel(),
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


def get_admin_log(self: Client, chat: Group | Channel | GroupRef | ChannelRef, /) -> AsyncList[RecentAction]:
    return RecentActionList(self, chat._ref)


class ProfilePhotoList(AsyncList[File]):
    def __init__(
        self,
        client: Client,
        peer: PeerRef,
    ):
        super().__init__()
        self._client = client
        self._peer = peer
        self._search_iter: Optional[SearchList] = None

    async def _fetch_next(self) -> None:
        if isinstance(self._peer, UserRef):
            result = await self._client(
                functions.photos.get_user_photos(
                    user_id=self._peer._to_input_user(),
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

            self._buffer.extend(filter(None, (File._try_from_raw_photo(self._client, p) for p in photos)))


def get_profile_photos(self: Client, peer: Peer | PeerRef, /) -> AsyncList[File]:
    return ProfilePhotoList(self, peer._ref)


async def set_participant_admin_rights(
    self: Client,
    chat: Group | Channel | GroupRef | ChannelRef,
    /,
    participant: User | UserRef,
    rights: Sequence[AdminRight],
) -> None:
    chat = chat._ref
    user = participant._ref
    if isinstance(chat, ChannelRef):
        admin_rights = AdminRight._set_to_raw(set(rights))
        await self(
            functions.channels.edit_admin(
                channel=chat._to_input_channel(),
                user_id=user._to_input_user(),
                admin_rights=admin_rights,
                rank="",
            )
        )
    else:
        await self(
            functions.messages.edit_chat_admin(
                chat_id=chat._to_input_chat(),
                user_id=user._to_input_user(),
                is_admin=bool(rights),
            )
        )


async def set_participant_restrictions(
    self: Client,
    chat: Group | Channel | GroupRef | ChannelRef,
    /,
    participant: Peer | PeerRef,
    restrictions: Sequence[ChatRestriction],
    *,
    until: Optional[datetime.datetime] = None,
) -> None:
    chat = chat._ref
    peer = participant._ref
    if isinstance(chat, ChannelRef):
        banned_rights = ChatRestriction._set_to_raw(
            set(restrictions),
            until_date=int(until.timestamp()) if until else 0x7FFFFFFF,
        )
        await self(
            functions.channels.edit_banned(
                channel=chat._to_input_channel(),
                participant=peer._to_input_peer(),
                banned_rights=banned_rights,
            )
        )
    elif isinstance(peer, UserRef):
        if restrictions:
            await self(
                functions.messages.delete_chat_user(
                    revoke_history=ChatRestriction.VIEW_MESSAGES in restrictions,
                    chat_id=chat._to_input_chat(),
                    user_id=peer._to_input_user(),
                )
            )


async def set_chat_default_restrictions(
    self: Client,
    chat: Peer | PeerRef,
    /,
    restrictions: Sequence[ChatRestriction],
    *,
    until: Optional[datetime.datetime] = None,
) -> None:
    banned_rights = ChatRestriction._set_to_raw(set(restrictions), int(until.timestamp()) if until else 0x7FFFFFFF)
    await self(
        functions.messages.edit_chat_default_banned_rights(peer=chat._ref._to_input_peer(), banned_rights=banned_rights)
    )
