from typing import Dict, Self

from ...tl import types
from .chat import Chat
from .meta import NoPublicConstructor


class Draft(metaclass=NoPublicConstructor):
    """
    A draft message in a chat.
    """

    __slots__ = ("_raw", "_chat_map")

    def __init__(
        self, raw: types.UpdateDraftMessage, chat_map: Dict[int, Chat]
    ) -> None:
        self._raw = raw
        self._chat_map = chat_map

    @classmethod
    def _from_raw(
        cls, draft: types.UpdateDraftMessage, chat_map: Dict[int, Chat]
    ) -> Self:
        return cls._create(draft, chat_map)

    async def delete(self) -> None:
        pass
