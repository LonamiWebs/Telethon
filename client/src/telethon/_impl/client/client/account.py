from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def takeout(self: Client) -> None:
    self
    raise NotImplementedError


async def end_takeout(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_2fa(self: Client) -> None:
    self
    raise NotImplementedError
