from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Optional, Self

from ...tl import abcs, functions, types
from ..types import ChatLike, InlineResult, NoPublicConstructor

if TYPE_CHECKING:
    from .client import Client


class InlineResults(metaclass=NoPublicConstructor):
    def __init__(
        self,
        client: Client,
        bot: types.InputUser,
        query: str,
        chat: abcs.InputPeer,
    ):
        self._client = client
        self._bot = bot
        self._query = query
        self._peer = chat or types.InputPeerEmpty()
        self._offset: Optional[str] = ""
        self._buffer: list[InlineResult] = []
        self._done = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> InlineResult:
        if not self._buffer:
            if self._offset is None:
                raise StopAsyncIteration

            result = await self._client(
                functions.messages.get_inline_bot_results(
                    bot=self._bot,
                    peer=self._peer,
                    geo_point=None,
                    query=self._query,
                    offset=self._offset,
                )
            )
            assert isinstance(result, types.messages.BotResults)
            self._offset = result.next_offset
            for r in reversed(result.results):
                assert isinstance(
                    r, (types.BotInlineMediaResult, types.BotInlineResult)
                )
                self._buffer.append(
                    InlineResult._create(self._client, result, r, self._peer)
                )

        if not self._buffer:
            self._offset = None
            raise StopAsyncIteration

        return self._buffer.pop()


async def inline_query(
    self: Client, bot: ChatLike, query: str = "", *, chat: Optional[ChatLike] = None
) -> AsyncIterator[InlineResult]:
    packed_bot = await self._resolve_to_packed(bot)
    packed_chat = await self._resolve_to_packed(chat) if chat else None
    return InlineResults._create(
        self,
        packed_bot._to_input_user(),
        query,
        packed_chat._to_input_peer() if packed_chat else types.InputPeerEmpty(),
    )
