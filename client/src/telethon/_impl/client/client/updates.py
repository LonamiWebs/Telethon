from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


async def set_receive_updates(self: Client) -> None:
    self
    raise NotImplementedError


def on(self: Client) -> None:
    self
    raise NotImplementedError


def add_event_handler(self: Client) -> None:
    self
    raise NotImplementedError


def remove_event_handler(self: Client) -> None:
    self
    raise NotImplementedError


def list_event_handlers(self: Client) -> None:
    self
    raise NotImplementedError


async def catch_up(self: Client) -> None:
    self
    raise NotImplementedError
