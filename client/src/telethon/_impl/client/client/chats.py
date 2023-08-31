from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def iter_participants(self: Client) -> None:
    self
    raise NotImplementedError


def iter_admin_log(self: Client) -> None:
    self
    raise NotImplementedError


def iter_profile_photos(self: Client) -> None:
    self
    raise NotImplementedError


def action(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_admin(self: Client) -> None:
    self
    raise NotImplementedError


async def edit_permissions(self: Client) -> None:
    self
    raise NotImplementedError


async def kick_participant(self: Client) -> None:
    self
    raise NotImplementedError


async def get_permissions(self: Client) -> None:
    self
    raise NotImplementedError


async def get_stats(self: Client) -> None:
    self
    raise NotImplementedError
