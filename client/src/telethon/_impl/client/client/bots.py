from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator, List, Optional, Self, Union

from ...._impl.tl import abcs, functions, types
from ..types.chat import ChatLike
from ..types.message import Message
from ..types.meta import NoPublicConstructor
from ..utils import generate_random_id

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
        self._buffer: List[InlineResult] = []
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


class InlineResult(metaclass=NoPublicConstructor):
    def __init__(
        self,
        client: Client,
        results: types.messages.BotResults,
        result: Union[types.BotInlineMediaResult, types.BotInlineResult],
        default_peer: abcs.InputPeer,
    ):
        self._client = client
        self._raw_results = results
        self._raw = result
        self._default_peer = default_peer

    @property
    def type(self) -> str:
        return self._raw.type

    @property
    def title(self) -> str:
        return self._raw.title or ""

    @property
    def description(self) -> Optional[str]:
        return self._raw.description

    async def send(
        self,
        chat: Optional[ChatLike],
    ) -> Message:
        if chat is None and isinstance(self._default_peer, types.InputPeerEmpty):
            raise ValueError("no target chat was specified")

        if chat is not None:
            peer = (await self._client._resolve_to_packed(chat))._to_input_peer()
        else:
            peer = self._default_peer

        random_id = generate_random_id()
        return self._client._build_message_map(
            await self._client(
                functions.messages.send_inline_bot_result(
                    silent=False,
                    background=False,
                    clear_draft=False,
                    hide_via=False,
                    peer=peer,
                    reply_to_msg_id=None,
                    top_msg_id=None,
                    random_id=random_id,
                    query_id=self._raw_results.query_id,
                    id=self._raw.id,
                    schedule_date=None,
                    send_as=None,
                )
            ),
            peer,
        ).with_random_id(random_id)


async def inline_query(
    self: Client, bot: ChatLike, query: str, *, chat: Optional[ChatLike] = None
) -> AsyncIterator[InlineResult]:
    packed_bot = await self._resolve_to_packed(bot)
    packed_chat = await self._resolve_to_packed(chat) if chat else None
    return InlineResults._create(
        self,
        packed_bot._to_input_user(),
        query,
        packed_chat._to_input_peer() if packed_chat else types.InputPeerEmpty(),
    )
