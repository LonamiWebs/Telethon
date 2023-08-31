from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


async def get_me(self: Client) -> None:
    self
    raise NotImplementedError


async def is_bot(self: Client) -> None:
    self
    raise NotImplementedError


async def is_user_authorized(self: Client) -> None:
    self
    raise NotImplementedError


async def get_entity(self: Client) -> None:
    self
    raise NotImplementedError


async def get_input_entity(self: Client) -> None:
    self
    raise NotImplementedError


async def get_peer_id(self: Client) -> None:
    self
    raise NotImplementedError
