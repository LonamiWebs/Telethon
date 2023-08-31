from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import Client


def build_reply_markup(self: Client) -> None:
    self
    raise NotImplementedError
