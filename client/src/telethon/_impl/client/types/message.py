from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Dict, Optional, Self

from ...tl import abcs, types
from ..parsers import generate_html_message, generate_markdown_message
from ..utils import expand_peer, peer_id
from .chat import Chat, ChatLike
from .file import File
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client import Client


class Message(metaclass=NoPublicConstructor):
    """
    A sent message.
    """

    __slots__ = ("_client", "_raw", "_chat_map")

    def __init__(
        self, client: Client, message: abcs.Message, chat_map: Dict[int, Chat]
    ) -> None:
        assert isinstance(
            message, (types.Message, types.MessageService, types.MessageEmpty)
        )
        self._client = client
        self._raw = message
        self._chat_map = chat_map

    @classmethod
    def _from_raw(
        cls, client: Client, message: abcs.Message, chat_map: Dict[int, Chat]
    ) -> Self:
        return cls._create(client, message, chat_map)

    @property
    def id(self) -> int:
        return self._raw.id

    @property
    def text(self) -> Optional[str]:
        return getattr(self._raw, "message", None)

    @property
    def text_html(self) -> Optional[str]:
        if text := getattr(self._raw, "message", None):
            return generate_html_message(
                text, getattr(self._raw, "entities", None) or []
            )
        else:
            return None

    @property
    def text_markdown(self) -> Optional[str]:
        if text := getattr(self._raw, "message", None):
            return generate_markdown_message(
                text, getattr(self._raw, "entities", None) or []
            )
        else:
            return None

    @property
    def date(self) -> Optional[datetime.datetime]:
        date = getattr(self._raw, "date", None)
        return (
            datetime.datetime.fromtimestamp(date, tz=datetime.timezone.utc)
            if date is not None
            else None
        )

    @property
    def chat(self) -> Chat:
        peer = self._raw.peer_id or types.PeerUser(user_id=0)
        broadcast = broadcast = getattr(self._raw, "post", None)
        return self._chat_map.get(peer_id(peer)) or expand_peer(
            peer, broadcast=broadcast
        )

    @property
    def sender(self) -> Optional[Chat]:
        if (from_ := getattr(self._raw, "from_id", None)) is not None:
            return self._chat_map.get(peer_id(from_)) or expand_peer(
                from_, broadcast=getattr(self._raw, "post", None)
            )
        else:
            return None

    def _file(self) -> Optional[File]:
        return (
            File._try_from_raw(self._raw.media)
            if isinstance(self._raw, types.Message) and self._raw.media
            else None
        )

    @property
    def photo(self) -> Optional[File]:
        photo = self._file()
        return photo if photo and photo._photo else None

    @property
    def audio(self) -> Optional[File]:
        audio = self._file()
        return (
            audio
            if audio
            and any(
                isinstance(a, types.DocumentAttributeAudio) for a in audio._attributes
            )
            else None
        )

    @property
    def video(self) -> Optional[File]:
        audio = self._file()
        return (
            audio
            if audio
            and any(
                isinstance(a, types.DocumentAttributeVideo) for a in audio._attributes
            )
            else None
        )

    @property
    def file(self) -> Optional[File]:
        return self._file()

    async def delete(self, *, revoke: bool = True) -> int:
        """
        Alias for :meth:`telethon.Client.delete_messages`.

        See the documentation of :meth:`~telethon.Client.delete_messages` for an explanation of the parameters.
        """
        return await self._client.delete_messages(self.chat, [self.id], revoke=revoke)

    async def edit(
        self,
        text: Optional[str] = None,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: Optional[bool] = None,
    ) -> Message:
        """
        Alias for :meth:`telethon.Client.edit_message`.

        See the documentation of :meth:`~telethon.Client.edit_message` for an explanation of the parameters.
        """
        return await self._client.edit_message(
            self.chat,
            self.id,
            text=text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
        )

    async def forward_to(self, target: ChatLike) -> Message:
        """
        Alias for :meth:`telethon.Client.forward_messages`.

        See the documentation of :meth:`~telethon.Client.forward_messages` for an explanation of the parameters.
        """
        return (await self._client.forward_messages(target, [self.id], self.chat))[0]
