from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def loop(self: Client) -> None:
    self
    raise NotImplementedError


def disconnected(self: Client) -> None:
    self
    raise NotImplementedError


def flood_sleep_threshold(self: Client) -> None:
    self
    raise NotImplementedError


async def connect(self: Client) -> None:
    self
    raise NotImplementedError


def is_connected(self: Client) -> None:
    self
    raise NotImplementedError


def disconnect(self: Client) -> None:
    self
    raise NotImplementedError


def set_proxy(self: Client) -> None:
    self
    raise NotImplementedError
