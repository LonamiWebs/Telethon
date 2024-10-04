from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional, Self, Sequence

from ...session import ChannelRef, GroupRef
from ...tl import abcs, types
from .admin_right import AdminRight
from .chat_restriction import ChatRestriction
from .meta import NoPublicConstructor
from .peer import Peer, User, peer_id

if TYPE_CHECKING:
    from ..client.client import Client


class Participant(metaclass=NoPublicConstructor):
    """
    A participant in a chat, including the corresponding user and permissions.

    You can obtain participants with methods such as :meth:`telethon.Client.get_participants`.
    """

    def __init__(
        self,
        client: Client,
        chat: GroupRef | ChannelRef,
        participant: (
            types.ChannelParticipant
            | types.ChannelParticipantSelf
            | types.ChannelParticipantCreator
            | types.ChannelParticipantAdmin
            | types.ChannelParticipantBanned
            | types.ChannelParticipantLeft
            | types.ChatParticipant
            | types.ChatParticipantCreator
            | types.ChatParticipantAdmin
        ),
        chat_map: dict[int, Peer],
    ) -> None:
        self._client = client
        self._chat = chat
        self._raw = participant
        self._chat_map = chat_map

    @classmethod
    def _from_raw_channel(
        cls,
        client: Client,
        chat: ChannelRef,
        participant: abcs.ChannelParticipant,
        chat_map: dict[int, Peer],
    ) -> Self:
        if isinstance(
            participant,
            (
                types.ChannelParticipant,
                types.ChannelParticipantSelf,
                types.ChannelParticipantCreator,
                types.ChannelParticipantAdmin,
                types.ChannelParticipantBanned,
                types.ChannelParticipantLeft,
            ),
        ):
            return cls._create(client, chat, participant, chat_map)
        else:
            raise RuntimeError("unexpected case")

    @classmethod
    def _from_raw_chat(
        cls,
        client: Client,
        chat: GroupRef,
        participant: abcs.ChatParticipant,
        chat_map: dict[int, Peer],
    ) -> Self:
        if isinstance(
            participant,
            (
                types.ChatParticipant,
                types.ChatParticipantCreator,
                types.ChatParticipantAdmin,
            ),
        ):
            return cls._create(client, chat, participant, chat_map)
        else:
            raise RuntimeError("unexpected case")

    def _peer_id(self) -> int:
        if isinstance(
            self._raw,
            (
                types.ChannelParticipant,
                types.ChannelParticipantSelf,
                types.ChannelParticipantCreator,
                types.ChannelParticipantAdmin,
                types.ChatParticipant,
                types.ChatParticipantCreator,
                types.ChatParticipantAdmin,
            ),
        ):
            return self._raw.user_id
        else:
            return peer_id(self._raw.peer)

    @property
    def user(self) -> Optional[User]:
        """
        The user participant that is currently present in the chat.

        This will be :data:`None` if the participant was instead :attr:`banned` or has :attr:`left`.
        """
        if isinstance(
            self._raw,
            (
                types.ChannelParticipant,
                types.ChannelParticipantSelf,
                types.ChannelParticipantCreator,
                types.ChannelParticipantAdmin,
                types.ChatParticipant,
                types.ChatParticipantCreator,
                types.ChatParticipantAdmin,
            ),
        ):
            user = self._chat_map[self._raw.user_id]
            assert isinstance(user, User)
            return user
        else:
            return None

    @property
    def banned(self) -> Optional[Peer]:
        """
        The banned participant.

        This will usually be a :class:`User`.
        """
        if isinstance(self._raw, types.ChannelParticipantBanned):
            return self._chat_map[peer_id(self._raw.peer)]
        else:
            return None

    @property
    def left(self) -> Optional[Peer]:
        """
        The participant that has left the group.

        This will usually be a :class:`User`.
        """
        if isinstance(self._raw, types.ChannelParticipantLeft):
            return self._chat_map[peer_id(self._raw.peer)]
        else:
            return None

    @property
    def creator(self) -> bool:
        """
        :data:`True` if the participant is the creator of the chat.
        """
        return isinstance(self._raw, (types.ChannelParticipantCreator, types.ChatParticipantCreator))

    @property
    def admin_rights(self) -> Optional[set[AdminRight]]:
        """
        The set of administrator rights this participant has been granted, if they are an administrator.
        """
        if isinstance(self._raw, (types.ChannelParticipantCreator, types.ChannelParticipantAdmin)):
            return AdminRight._from_raw(self._raw.admin_rights)
        elif isinstance(self._raw, (types.ChatParticipantCreator, types.ChatParticipantAdmin)):
            return AdminRight._chat_rights()
        else:
            return None

    @property
    def restrictions(self) -> Optional[set[ChatRestriction]]:
        """
        The set of restrictions applied to this participant, if they are banned.
        """
        if isinstance(self._raw, types.ChannelParticipantBanned):
            return ChatRestriction._from_raw(self._raw.banned_rights)
        else:
            return None

    async def set_admin_rights(self, rights: Sequence[AdminRight]) -> None:
        """
        Alias for :meth:`telethon.Client.set_participant_admin_rights`.
        """
        participant = self.user or self.banned or self.left
        assert participant
        if isinstance(participant, User):
            await self._client.set_participant_admin_rights(self._chat, participant, rights)
        else:
            raise TypeError(f"participant of type {participant.__class__.__name__} cannot be made admin")

    async def set_restrictions(
        self,
        restrictions: Sequence[ChatRestriction],
        *,
        until: Optional[datetime.datetime] = None,
    ) -> None:
        """
        Alias for :meth:`telethon.Client.set_participant_restrictions`.
        """
        participant = self.user or self.banned or self.left
        assert participant
        await self._client.set_participant_restrictions(self._chat, participant, restrictions, until=until)
