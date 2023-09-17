from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Dict, Optional, Self

from ...tl import abcs
from ..types import Chat, NoPublicConstructor

if TYPE_CHECKING:
    from ..client.client import Client


class Event(metaclass=NoPublicConstructor):
    """
    The base type of all events.
    """

    @classmethod
    @abc.abstractmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        pass
