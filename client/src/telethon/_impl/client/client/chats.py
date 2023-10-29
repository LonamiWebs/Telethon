from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...tl import abcs, functions, types
from ..types import AsyncList, ChatLike, File, Participant, RecentAction, build_chat_map
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
        self._peer: Optional[abcs.InputPeer] = None
        self._offset = 0

    async def _fetch_next(self) -> None:
        if self._peer is None:
            self._peer = (
                await self._client._resolve_to_packed(self._chat)
            )._to_input_peer()

        if isinstance(self._peer, types.InputPeerChannel):
            result = await self._client(
                functions.channels.get_participants(
                    channel=types.InputChannel(
                        channel_id=self._peer.channel_id,
                        access_hash=self._peer.access_hash,
                    ),
                    filter=types.ChannelParticipantsRecent(),
                    offset=self._offset,
                    limit=200,
                    hash=0,
                )
            )
            assert isinstance(result, types.channels.ChannelParticipants)

            chat_map = build_chat_map(result.users, result.chats)

            self._buffer.extend(
                Participant._from_raw_channel(p, chat_map) for p in result.participants
            )
            self._total = result.count

        elif isinstance(self._peer, types.InputPeerChat):
            result = await self._client(
                functions.messages.get_full_chat(chat_id=self._peer.chat_id)  # type: ignore [arg-type]
            )
            assert isinstance(result, types.messages.ChatFull)
            assert isinstance(result.full_chat, types.ChatFull)

            chat_map = build_chat_map(result.users, result.chats)

            participants = result.full_chat.participants
            if isinstance(participants, types.ChatParticipantsForbidden):
                if participants.self_participant:
                    self._buffer.append(
                        Participant._from_raw_chat(
                            participants.self_participant, chat_map
                        )
                    )
            elif isinstance(participants, types.ChatParticipants):
                self._buffer.extend(
                    Participant._from_raw_chat(p, chat_map)
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

        chat_map = build_chat_map(result.users, result.chats)
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


def set_banned_rights(self: Client, chat: ChatLike, user: ChatLike) -> None:
    pass


def set_admin_rights(self: Client, chat: ChatLike, user: ChatLike) -> None:
    pass


def set_default_rights(self: Client, chat: ChatLike, user: ChatLike) -> None:
    pass
