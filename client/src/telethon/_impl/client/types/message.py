from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Dict, Optional, Self, Union

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
        """
        The message identifier.

        .. seealso::

            :doc:`/concepts/messages`, which contains an in-depth explanation of message counters.
        """
        return self._raw.id

    @property
    def grouped_id(self) -> Optional[int]:
        """
        If the message is grouped with others in an album, return the group identifier.

        Messages with the same :attr:`grouped_id` will belong to the same album.

        Note that there can be messages in-between that do not have a :attr:`grouped_id`.
        """
        return getattr(self._raw, "grouped_id", None)

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
            File._try_from_raw_message_media(self._client, self._raw.media)
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

    @property
    def replied_message_id(self) -> Optional[int]:
        """
        Get the message identifier of the replied message.

        .. seealso::

            :meth:`get_reply_message`
        """
        if header := getattr(self._raw, "reply_to", None):
            return getattr(header, "reply_to_msg_id", None)

        return None

    async def get_reply_message(self) -> Optional[Message]:
        """
        Alias for :meth:`telethon.Client.get_messages_with_ids`.

        If all you want is to check whether this message is a reply, use :attr:`replied_message_id`.
        """
        if self.replied_message_id is not None:
            from ..client.messages import CherryPickedList

            lst = CherryPickedList(self._client, self.chat, [])
            lst._ids.append(types.InputMessageReplyTo(id=self.id))
            return (await lst)[0]
        return None

    async def respond(
        self,
        text: Optional[Union[str, Message]] = None,
        *,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
    ) -> Message:
        """
        Alias for :meth:`telethon.Client.send_message`.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :meth:`~telethon.Client.send_message`.
        """
        return await self._client.send_message(
            self.chat, text, markdown=markdown, html=html, link_preview=link_preview
        )

    async def reply(
        self,
        text: Optional[Union[str, Message]] = None,
        *,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
    ) -> Message:
        """
        Alias for :meth:`telethon.Client.send_message` with the ``reply_to`` parameter set to this message.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :meth:`~telethon.Client.send_message`.
        """
        return await self._client.send_message(
            self.chat,
            text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
            reply_to=self.id,
        )

    async def delete(self, *, revoke: bool = True) -> None:
        """
        Alias for :meth:`telethon.Client.delete_messages`.

        :param revoke: See :meth:`~telethon.Client.delete_messages`.
        """
        await self._client.delete_messages(self.chat, [self.id], revoke=revoke)

    async def edit(
        self,
        text: Optional[str] = None,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: Optional[bool] = None,
    ) -> Message:
        """
        Alias for :meth:`telethon.Client.edit_message`.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :meth:`~telethon.Client.send_message`.
        """
        return await self._client.edit_message(
            self.chat,
            self.id,
            text=text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
        )

    async def forward(self, target: ChatLike) -> Message:
        """
        Alias for :meth:`telethon.Client.forward_messages`.

        :param target: See :meth:`~telethon.Client.forward_messages`.
        """
        return (await self._client.forward_messages(target, [self.id], self.chat))[0]

    async def mark_read(self) -> None:
        pass

    async def pin(self) -> None:
        """
        Alias for :meth:`telethon.Client.pin_message`.
        """
        pass

    async def unpin(self) -> None:
        """
        Alias for :meth:`telethon.Client.unpin_message`.
        """
        pass

    # ---

    @property
    def forward_info(self) -> None:
        pass

    @property
    def buttons(self) -> None:
        pass

    @property
    def web_preview(self) -> None:
        pass

    @property
    def voice(self) -> None:
        pass

    @property
    def video_note(self) -> None:
        pass

    @property
    def gif(self) -> None:
        pass

    @property
    def sticker(self) -> None:
        pass

    @property
    def contact(self) -> None:
        pass

    @property
    def game(self) -> None:
        pass

    @property
    def geo(self) -> None:
        pass

    @property
    def invoice(self) -> None:
        pass

    @property
    def poll(self) -> None:
        pass

    @property
    def venue(self) -> None:
        pass

    @property
    def dice(self) -> None:
        pass

    @property
    def via_bot(self) -> None:
        pass

    @property
    def silent(self) -> bool:
        return getattr(self._raw, "silent", None) or False

    @property
    def can_forward(self) -> bool:
        if isinstance(self._raw, types.Message):
            return not self._raw.noforwards
        else:
            return False
