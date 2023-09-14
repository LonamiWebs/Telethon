from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from ...tl import abcs
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class CallbackQuery(Event):
    """
    Occurs when an inline button was pressed.

    Only bot accounts can receive this event.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()


class InlineQuery(Event):
    """
    Occurs when users type ``@bot query`` in their chat box.

    Only bot accounts can receive this event.
    """

    @classmethod
    def _try_from_update(cls, client: Client, update: abcs.Update) -> Optional[Self]:
        raise NotImplementedError()
