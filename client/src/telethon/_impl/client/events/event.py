from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Optional, Self

from ...tl import abcs
from ..types import NoPublicConstructor, Peer

if TYPE_CHECKING:
    from ..client.client import Client


class Event(abc.ABC, metaclass=NoPublicConstructor):
    """
    The base type of all events.
    """

    @property
    def client(self) -> Client:
        """
        The :class:`~telethon.Client` that received this update.
        """
        return getattr(self, "_client")  # type: ignore [no-any-return]

    @classmethod
    @abc.abstractmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: dict[int, Peer]
    ) -> Optional[Self]:
        pass


class Raw(Event):
    """
    Raw update type received from Telegram.

    This event occurs when *any* update is received.

    Like every other event, the raw update type is under the private member ``event._raw``.

    Additionally, all peers received along with this update are present under ``self._chat_map``.
    """

    def __init__(
        self,
        client: Client,
        update: abcs.Update,
        chat_map: dict[int, Peer],
    ) -> None:
        self._client = client
        self._raw = update
        self._chat_map = chat_map

    @classmethod
    def _try_from_update(
        cls, client: Client, update: abcs.Update, chat_map: dict[int, Peer]
    ) -> Optional[Self]:
        return cls._create(client, update, chat_map)


class Continue:
    """
    This is **not** an event type you can listen to.

    This is a sentinel value used to signal that the library should *Continue* calling other handlers.

    You can :keyword:`return` this from your handlers if you want handlers registered after to also run.

    The primary use case is having asynchronous filters inside your handler:

    .. code-block:: python

        from telethon import events

        @client.on(events.NewMessage)
        async def admin_only_handler(event):
            allowed = await database.is_user_admin(event.sender.id)
            if not allowed:
                # this user is not allowed, fall-through the handlers
                return events.Continue

        @client.on(events.NewMessage)
        async def everyone_else_handler(event):
            ...  # runs if admin_only_handler was not allowed
    """

    def __init__(self) -> None:
        raise TypeError(
            f"Can't instantiate {self.__class__.__name__} class (the type is the sentinel value; remove the parenthesis)"
        )
