from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional, Self

from ...tl import abcs
from ..types.meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client.client import Client


class Event(metaclass=NoPublicConstructor):
    @classmethod
    @abc.abstractmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        pass
