from typing import Dict, Optional, Self, Set, Union

from ...tl import abcs, types
from .admin_right import AdminRight
from .chat import Chat, User, peer_id
from .meta import NoPublicConstructor


class Participant(metaclass=NoPublicConstructor):
    """
    A participant in a chat, including the corresponding user and permissions.

    You can obtain participants with methods such as :meth:`telethon.Client.get_participants`.
    """

    __slots__ = ("_raw", "_chat_map")

    def __init__(
        self,
        participant: Union[
            types.ChannelParticipant,
            types.ChannelParticipantSelf,
            types.ChannelParticipantCreator,
            types.ChannelParticipantAdmin,
            types.ChannelParticipantBanned,
            types.ChannelParticipantLeft,
            types.ChatParticipant,
            types.ChatParticipantCreator,
            types.ChatParticipantAdmin,
        ],
        chat_map: Dict[int, Chat],
    ) -> None:
        self._raw = participant
        self._chat_map = chat_map

    @classmethod
    def _from_raw_channel(
        cls, participant: abcs.ChannelParticipant, chat_map: Dict[int, Chat]
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
            return cls._create(participant, chat_map)
        else:
            raise RuntimeError("unexpected case")

    @classmethod
    def _from_raw_chat(
        cls, participant: abcs.ChatParticipant, chat_map: Dict[int, Chat]
    ) -> Self:
        if isinstance(
            participant,
            (
                types.ChatParticipant,
                types.ChatParticipantCreator,
                types.ChatParticipantAdmin,
            ),
        ):
            return cls._create(participant, chat_map)
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
        elif isinstance(
            self._raw, (types.ChannelParticipantBanned, types.ChannelParticipantLeft)
        ):
            return peer_id(self._raw.peer)
        else:
            raise RuntimeError("unexpected case")

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
    def banned(self) -> Optional[Chat]:
        """
        The banned participant.

        This will usually be a :class:`User`.
        """
        if isinstance(self._raw, types.ChannelParticipantBanned):
            return self._chat_map[peer_id(self._raw.peer)]
        else:
            return None

    @property
    def left(self) -> Optional[Chat]:
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
        return isinstance(
            self._raw, (types.ChannelParticipantCreator, types.ChatParticipantCreator)
        )

    @property
    def admin_rights(self) -> Optional[Set[AdminRight]]:
        """
        The set of administrator rights this participant has been granted, if they are an administrator.
        """
        if isinstance(
            self._raw, (types.ChannelParticipantCreator, types.ChannelParticipantAdmin)
        ):
            return AdminRight._from_raw(self._raw.admin_rights)
        elif isinstance(
            self._raw, (types.ChatParticipantCreator, types.ChatParticipantAdmin)
        ):
            return AdminRight._chat_rights()
        else:
            return None
