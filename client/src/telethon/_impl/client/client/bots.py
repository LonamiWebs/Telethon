from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


async def inline_query(self: Client) -> None:
    self
    raise NotImplementedError
