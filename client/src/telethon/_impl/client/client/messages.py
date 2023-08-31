from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def iter_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def send_message(self: Client) -> None:
    self
    raise NotImplementedError


async def forward_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_message(self: Client) -> None:
    self
    raise NotImplementedError


async def delete_messages(self: Client) -> None:
    self
    raise NotImplementedError


async def send_read_acknowledge(self: Client) -> None:
    self
    raise NotImplementedError


async def pin_message(self: Client) -> None:
    self
    raise NotImplementedError


async def unpin_message(self: Client) -> None:
    self
    raise NotImplementedError
