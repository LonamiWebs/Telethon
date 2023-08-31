from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


async def send_file(self: Client) -> None:
    self
    raise NotImplementedError


async def upload_file(self: Client) -> None:
    self
    raise NotImplementedError
