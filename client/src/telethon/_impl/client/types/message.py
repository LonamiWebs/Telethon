from __future__ import annotations

import datetime
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Self, Union

from ...tl import abcs, types
from ..parsers import generate_html_message, generate_markdown_message
from .buttons import Button, as_concrete_row, create_button
from .chat import Chat, ChatLike, expand_peer, peer_id
from .file import File
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client.client import Client


_last_id = 0


def generate_random_id() -> int:
    global _last_id
    if _last_id == 0:
        _last_id = int(time.time() * 1e9)
    _last_id += 1
    return _last_id


def adapt_date(date: Optional[int]) -> Optional[datetime.datetime]:
    return (
        datetime.datetime.fromtimestamp(date, tz=datetime.timezone.utc)
        if date is not None
        else None
    )


class Message(metaclass=NoPublicConstructor):
    """
    A sent message.

    You can get a message from :class:`telethon.events.NewMessage`,
    or from methods such as :meth:`telethon.Client.get_messages`.
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

    @classmethod
    def _from_defaults(
        cls,
        client: Client,
        chat_map: Dict[int, Chat],
        id: int,
        peer_id: abcs.Peer,
        date: int,
        message: str,
        **kwargs: Any,
    ) -> Self:
        default_kwargs: Dict[str, Any] = {
            "out": False,
            "mentioned": False,
            "media_unread": False,
            "silent": False,
            "post": False,
            "from_scheduled": False,
            "legacy": False,
            "edit_hide": False,
            "pinned": False,
            "noforwards": False,
            "id": id,
            "from_id": None,
            "peer_id": peer_id,
            "fwd_from": None,
            "via_bot_id": None,
            "reply_to": None,
            "date": date,
            "message": message,
            "media": None,
            "reply_markup": None,
            "entities": None,
            "views": None,
            "forwards": None,
            "replies": None,
            "edit_date": None,
            "post_author": None,
            "grouped_id": None,
            "reactions": None,
            "restriction_reason": None,
            "ttl_period": None,
        }
        default_kwargs.update(kwargs)
        return cls._create(client, types.Message(**default_kwargs), chat_map)

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
        """
        The message text without any formatting.
        """
        return getattr(self._raw, "message", None)

    @property
    def text_html(self) -> Optional[str]:
        """
        The message text formatted using standard `HTML elements <https://developer.mozilla.org/en-US/docs/Web/HTML/Element>`_.

        See :ref:`formatting` to learn the HTML elements used.
        """
        if text := getattr(self._raw, "message", None):
            return generate_html_message(
                text, getattr(self._raw, "entities", None) or []
            )
        else:
            return None

    @property
    def text_markdown(self) -> Optional[str]:
        """
        The message text formatted as `CommonMark's markdown <https://commonmark.org/>`_.

        See :ref:`formatting` to learn the formatting characters used.
        """
        if text := getattr(self._raw, "message", None):
            return generate_markdown_message(
                text, getattr(self._raw, "entities", None) or []
            )
        else:
            return None

    @property
    def date(self) -> Optional[datetime.datetime]:
        """
        The date when the message was sent.
        """
        return adapt_date(getattr(self._raw, "date", None))

    @property
    def chat(self) -> Chat:
        """
        The :term:`chat` when the message was sent.
        """
        peer = self._raw.peer_id or types.PeerUser(user_id=0)
        pid = peer_id(peer)
        if pid not in self._chat_map:
            self._chat_map[pid] = expand_peer(
                self._client, peer, broadcast=getattr(self._raw, "post", None)
            )
        return self._chat_map[pid]

    @property
    def sender(self) -> Optional[Chat]:
        """
        The :term:`chat` that sent the message.

        This will usually be a :class:`User`, but can also be a :class:`Channel`.

        If there is no sender, it means the message was sent by an anonymous user.
        """
        if (from_ := getattr(self._raw, "from_id", None)) is not None:
            return self._chat_map.get(peer_id(from_)) or expand_peer(
                self._client, from_, broadcast=getattr(self._raw, "post", None)
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
        """
        The compressed photo media :attr:`file` in the message.

        This can also be used as a way to check that the message media is a photo.
        """
        photo = self._file()
        return photo if photo and photo._photo else None

    @property
    def audio(self) -> Optional[File]:
        """
        The audio media :attr:`file` in the message.

        This can also be used as a way to check that the message media is an audio.
        """
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
        """
        The video media :attr:`file` in the message.

        This can also be used as a way to check that the message media is a video.
        """
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
        """
        The downloadable file in the message.

        This might also come from a link preview.

        Unlike :attr:`photo`, :attr:`audio` and :attr:`video`,
        this property does not care about the media type, only whether it can be downloaded.

        This means the file will be :data:`None` for other media types, such as polls, venues or contacts.
        """
        return self._file()

    @property
    def replied_message_id(self) -> Optional[int]:
        """
        Get the message identifier of the replied message.

        .. seealso::

            :meth:`get_replied_message`
        """
        if header := getattr(self._raw, "reply_to", None):
            return getattr(header, "reply_to_msg_id", None)

        return None

    async def get_replied_message(self) -> Optional[Message]:
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
        buttons: Optional[Union[List[Button], List[List[Button]]]] = None,
    ) -> Message:
        """
        Alias for :meth:`telethon.Client.send_message`.

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
            buttons=buttons,
        )

    async def reply(
        self,
        text: Optional[Union[str, Message]] = None,
        *,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
        buttons: Optional[Union[List[Button], List[List[Button]]]] = None,
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
            buttons=buttons,
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
        link_preview: bool = False,
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

    async def read(self) -> None:
        """
        Alias for :meth:`telethon.Client.read_message`.
        """
        await self._client.read_message(self.chat, self.id)

    async def pin(self) -> Message:
        """
        Alias for :meth:`telethon.Client.pin_message`.
        """
        return await self._client.pin_message(self.chat, self.id)

    async def unpin(self) -> None:
        """
        Alias for :meth:`telethon.Client.unpin_message`.
        """
        await self._client.unpin_message(self.chat, self.id)

    # ---

    @property
    def forward_info(self) -> None:
        pass

    @property
    def buttons(self) -> Optional[List[List[Button]]]:
        """
        The buttons attached to the message.

        These are displayed under the message if they are :class:`~telethon.types.InlineButton`,
        and replace the user's virtual keyboard otherwise.

        The returned value is a list of rows, each row having a list of buttons, one per column.
        The amount of columns in each row can vary. For example:

        .. code-block:: python

            buttons = [
                [col_0,        col_1],  # row 0
                [       col_0       ],  # row 1
                [col_0, col_1, col_2],  # row 2
            ]

            row = 2
            col = 1
            button = buttons[row][col]  # the middle button on the bottom row
        """
        markup = getattr(self._raw, "reply_markup", None)
        if not isinstance(markup, (types.ReplyKeyboardMarkup, types.ReplyInlineMarkup)):
            return None

        return [
            [create_button(self, button) for button in row.buttons]
            for row in map(as_concrete_row, markup.rows)
        ]

    @property
    def link_preview(self) -> None:
        pass

    @property
    def silent(self) -> bool:
        """
        :data:`True` if the message is silent and should not cause a notification.
        """
        return getattr(self._raw, "silent", None) or False

    @property
    def can_forward(self) -> bool:
        if isinstance(self._raw, types.Message):
            return not self._raw.noforwards
        else:
            return False


def build_msg_map(
    client: Client, messages: List[abcs.Message], chat_map: Dict[int, Chat]
) -> Dict[int, Message]:
    return {
        msg.id: msg
        for msg in (Message._from_raw(client, m, chat_map) for m in messages)
    }
