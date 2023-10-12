from typing import Dict, Self, Union

from ...tl import abcs, types
from .chat import Chat
from .meta import NoPublicConstructor


class Participant(metaclass=NoPublicConstructor):
    """
    A participant in a chat, including the corresponding user and permissions.
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
