from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def start(self: Client) -> None:
    self
    raise NotImplementedError


async def sign_in(self: Client) -> None:
    self
    raise NotImplementedError


async def sign_up(self: Client) -> None:
    self
    raise NotImplementedError


async def send_code_request(self: Client) -> None:
    self
    raise NotImplementedError


async def qr_login(self: Client) -> None:
    self
    raise NotImplementedError


async def log_out(self: Client) -> None:
    self
    raise NotImplementedError
