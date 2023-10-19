from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from ...tl import abcs, functions, types
from .chat import ChatLike
from .message import Message
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client import Client


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
        chat: Optional[ChatLike] = None,
    ) -> Message:
        """
        Send the inline result to the desired chat.

        :param chat:
            The chat where the inline result should be sent to.

            This can be omitted if a chat was previously specified in the :meth:`~telethon.Client.inline_query`.

        :return: The sent message.
        """
        from ..utils import generate_random_id

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
                    reply_to=None,
                    random_id=random_id,
                    query_id=self._raw_results.query_id,
                    id=self._raw.id,
                    schedule_date=None,
                    send_as=None,
                )
            ),
            peer,
        ).with_random_id(random_id)
