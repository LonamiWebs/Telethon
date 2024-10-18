from __future__ import annotations

import weakref
from asyncio import BufferedProtocol, Event
from typing import TYPE_CHECKING, Literal

from typing_extensions import Buffer

if TYPE_CHECKING:
    from .sender import Sender


class BufferedStreamingProtocol(BufferedProtocol):
    __slots__ = ("_sender", "_closed")

    def __init__(self, sender: Sender) -> None:
        self._sender = weakref.ref(sender)
        self._closed = Event()

    @property
    def sender(self) -> Sender:
        if (sender := self._sender()) is None:
            raise ValueError("Sender has been garbage-collected")
        return sender

    # Method overrides

    def get_buffer(self, sizehint: int) -> Buffer:
        return self.sender._read_buffer

    def buffer_updated(self, nbytes: int) -> None:
        self.sender._on_buffer_updated(nbytes)

    def connection_lost(self, exc: Exception | None) -> None:
        self._closed.set()

    # Custom methods

    def is_closed(self) -> bool:
        return self._closed.is_set()

    async def wait_closed(self) -> Literal[True]:
        return await self._closed.wait()
