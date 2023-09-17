from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...tl import abcs, functions, types
from ..types import AsyncList, ChatLike, Participant
from ..utils import build_chat_map

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
