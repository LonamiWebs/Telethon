from __future__ import annotations

import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from ...session import Gap
from ...tl import abcs
from ..events import Continue
from ..events import Event as EventBase
from ..events.filters import Filter
from ..types import build_chat_map

if TYPE_CHECKING:
    from .client import Client

Event = TypeVar("Event", bound=EventBase)

UPDATE_LIMIT_EXCEEDED_LOG_COOLDOWN = 300


def on(
    self: Client, event_cls: Type[Event], filter: Optional[Filter] = None
) -> Callable[[Callable[[Event], Awaitable[Any]]], Callable[[Event], Awaitable[Any]]]:
    def wrapper(
        handler: Callable[[Event], Awaitable[Any]]
    ) -> Callable[[Event], Awaitable[Any]]:
        add_event_handler(self, handler, event_cls, filter)
        return handler

    return wrapper


def add_event_handler(
    self: Client,
    handler: Callable[[Event], Awaitable[Any]],
    event_cls: Type[Event],
    filter: Optional[Filter] = None,
) -> None:
    self._handlers.setdefault(event_cls, []).append((handler, filter))


def remove_event_handler(
    self: Client, handler: Callable[[Event], Awaitable[Any]]
) -> None:
    for event_cls, handlers in tuple(self._handlers.items()):
        for i in reversed(range(len(handlers))):
            if handlers[i][0] == handler:
                handlers.pop(i)
        if not handlers:
            del self._handlers[event_cls]


def get_handler_filter(
    self: Client, handler: Callable[[Event], Awaitable[Any]]
) -> Optional[Filter]:
    for handlers in self._handlers.values():
        for h, f in handlers:
            if h == handler:
                return f
    return None


def set_handler_filter(
    self: Client,
    handler: Callable[[Event], Awaitable[Any]],
    filter: Optional[Filter] = None,
) -> None:
    for handlers in self._handlers.values():
        for i, (h, _) in enumerate(handlers):
            if h == handler:
                handlers[i] = (h, filter)


def process_socket_updates(client: Client, all_updates: List[abcs.Updates]) -> None:
    if not all_updates:
        return

    for updates in all_updates:
        try:
            client._message_box.ensure_known_peer_hashes(updates, client._chat_hashes)
        except Gap:
            return

        try:
            result, users, chats = client._message_box.process_updates(
                updates, client._chat_hashes
            )
        except Gap:
            return

        extend_update_queue(client, result, users, chats)


def extend_update_queue(
    client: Client,
    updates: List[abcs.Update],
    users: Sequence[abcs.User],
    chats: Sequence[abcs.Chat],
) -> None:
    chat_map = build_chat_map(client, users, chats)

    for update in updates:
        try:
            client._updates.put_nowait((update, chat_map))
        except asyncio.QueueFull:
            now = asyncio.get_running_loop().time()
            if client._last_update_limit_warn is None or (
                now - client._last_update_limit_warn
                > UPDATE_LIMIT_EXCEEDED_LOG_COOLDOWN
            ):
                client._config.base_logger.warning(
                    "updates are being dropped because limit=%d has been reached",
                    client._updates.maxsize,
                )
                client._last_update_limit_warn = now
            break


async def dispatcher(client: Client) -> None:
    loop = asyncio.get_running_loop()
    while client.connected:
        try:
            await dispatch_next(client)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if isinstance(e, RuntimeError) and loop.is_closed():
                # User probably forgot to call disconnect.
                client._config.base_logger.warning(
                    "client was not closed cleanly, make sure to call client.disconnect()! %s",
                    e,
                )
                return
            else:
                client._config.base_logger.exception(
                    "unhandled exception in event handler; this is probably a bug in your code, not telethon"
                )
                raise


async def dispatch_next(client: Client) -> None:
    update, chat_map = await client._updates.get()
    for event_cls, handlers in client._handlers.items():
        if event := event_cls._try_from_update(client, update, chat_map):
            for handler, filter in handlers:
                if not filter or filter(event):
                    ret = await handler(event)
                    if not (ret is Continue or client._check_all_handlers):
                        return
