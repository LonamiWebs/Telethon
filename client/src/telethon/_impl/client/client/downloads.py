from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


async def download_profile_photo(self: Client) -> None:
    self
    raise NotImplementedError


async def download_media(self: Client) -> None:
    self
    raise NotImplementedError


def iter_download(self: Client) -> None:
    self
    raise NotImplementedError
