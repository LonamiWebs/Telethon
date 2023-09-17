from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, Self

from ...tl import abcs, types
from ..types import Chat
from .event import Event

if TYPE_CHECKING:
    from ..client.client import Client


class CallbackQuery(Event):
    """
    Occurs when an inline button was pressed.

    Only bot accounts can receive this event.
    """

    def __init__(self, update: types.UpdateBotCallbackQuery):
        self._update = update

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateBotCallbackQuery):
            return cls._create(update)
        else:
            return None


class InlineQuery(Event):
    """
    Occurs when users type ``@bot query`` in their chat box.

    Only bot accounts can receive this event.
    """

    def __init__(self, update: types.UpdateBotInlineQuery):
        self._update = update

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: Dict[int, Chat]
    ) -> Optional[Self]:
        if isinstance(update, types.UpdateBotInlineQuery):
            return cls._create(update)
        else:
            return None
