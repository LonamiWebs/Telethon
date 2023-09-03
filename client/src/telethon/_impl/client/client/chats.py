from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def get_participants(self: Client) -> None:
    self
    raise NotImplementedError
