from typing import Dict, List, Optional, Self

from ...session import PackedChat, PackedType
from ...tl import abcs, types
from .chat import Chat
from .meta import NoPublicConstructor


class Dialog(metaclass=NoPublicConstructor):
    """
    A dialog.

    This represents an open conversation your chat list.

    This includes the groups you've joined, channels you've subscribed to, and open one-to-one private conversations.
    """

    __slots__ = ("_raw", "_chat_map")

    def __init__(self, raw: abcs.Dialog, chat_map: Dict[int, Chat]) -> None:
        self._raw = raw
        self._chat_map = chat_map

    @classmethod
    def _from_raw(cls, dialog: abcs.Dialog, chat_map: Dict[int, Chat]) -> Self:
        return cls._create(dialog, chat_map)
