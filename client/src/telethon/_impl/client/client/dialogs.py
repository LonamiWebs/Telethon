from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def iter_dialogs(self: Client) -> None:
    self
    raise NotImplementedError


def iter_drafts(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_folder(self: Client) -> None:
    self
    raise NotImplementedError


async def delete_dialog(self: Client) -> None:
    self
    raise NotImplementedError


def conversation(self: Client) -> None:
    self
    raise NotImplementedError
