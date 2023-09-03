from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def get_dialogs(self: Client) -> None:
    self
    raise NotImplementedError


async def delete_dialog(self: Client) -> None:
    self
    raise NotImplementedError
