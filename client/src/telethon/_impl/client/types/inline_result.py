from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...session import PeerRef
from ...tl import functions, types
from .message import Message, generate_random_id
from .meta import NoPublicConstructor
from .peer import Peer

if TYPE_CHECKING:
    from ..client.client import Client


class InlineResult(metaclass=NoPublicConstructor):
    """
    A single inline result from an inline query made to a bot.

    This is returned when calling :meth:`telethon.Client.inline_query`.
    """

    def __init__(
        self,
        client: Client,
        results: types.messages.BotResults,
        result: types.BotInlineMediaResult | types.BotInlineResult,
        default_peer: Optional[PeerRef],
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
        """
        The title of the result, or the empty string if there is none.
        """
        return self._raw.title or ""

    @property
    def description(self) -> Optional[str]:
        """
        The description of the result, if available.
        """
        return self._raw.description

    async def send(
        self,
        peer: Optional[Peer | PeerRef] = None,
    ) -> Message:
        """
        Send the result to the desired chat.

        :param chat:
            The chat where the inline result should be sent to.

            This can be omitted if a chat was previously specified in the :meth:`~telethon.Client.inline_query`.

        :return: The sent message.
        """
        if peer is None:
            if self._default_peer is None:
                raise ValueError("no target chat was specified")
            peer = self._default_peer
        else:
            peer = peer._ref

        random_id = generate_random_id()
        return self._client._build_message_map(
            await self._client(
                functions.messages.send_inline_bot_result(
                    silent=False,
                    background=False,
                    clear_draft=False,
                    hide_via=False,
                    peer=peer._to_input_peer(),
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
