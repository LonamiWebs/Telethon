from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ...session import PeerRef
from ...tl import abcs, functions, types
from .file import InFileLike, try_get_url_path
from .message import Message, generate_random_id, parse_message
from .meta import NoPublicConstructor
from .peer import Peer

if TYPE_CHECKING:
    from ..client.client import Client


class AlbumBuilder(metaclass=NoPublicConstructor):
    """
    Album builder to prepare albums with multiple files before sending it all at once.

    This class is constructed by calling :meth:`telethon.Client.prepare_album`.
    """

    def __init__(self, *, client: Client) -> None:
        self._client = client
        self._medias: list[types.InputSingleMedia] = []

    async def add_photo(
        self,
        file: str | Path | InFileLike,
        *,
        size: Optional[int] = None,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
    ) -> None:
        """
        Add a photo to the album.

        :param file:
            The photo to attach to the album.

            This behaves the same way as the file parameter in :meth:`telethon.Client.send_file`,
            *except* that it cannot be previously-sent media.

        :param size: See :meth:`telethon.Client.send_file`.
        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.
        """
        input_media: abcs.InputMedia
        if try_get_url_path(file) is not None:
            assert isinstance(file, str)
            input_media = types.InputMediaPhotoExternal(
                spoiler=False, url=file, ttl_seconds=None
            )
        else:
            input_file, _ = await self._client._upload(file, size, "a.jpg")
            input_media = types.InputMediaUploadedPhoto(
                spoiler=False, file=input_file, stickers=None, ttl_seconds=None
            )

        media = await self._client(
            functions.messages.upload_media(
                peer=types.InputPeerSelf(), media=input_media
            )
        )
        assert isinstance(media, types.MessageMediaPhoto)
        assert isinstance(media.photo, types.Photo)
        input_media = types.InputMediaPhoto(
            spoiler=media.spoiler,
            id=types.InputPhoto(
                id=media.photo.id,
                access_hash=media.photo.access_hash,
                file_reference=media.photo.file_reference,
            ),
            ttl_seconds=media.ttl_seconds,
        )
        message, entities = parse_message(
            text=caption, markdown=caption_markdown, html=caption_html, allow_empty=True
        )
        self._medias.append(
            types.InputSingleMedia(
                media=input_media,
                random_id=generate_random_id(),
                message=message,
                entities=entities,
            )
        )

    async def add_video(
        self,
        file: str | Path | InFileLike,
        *,
        size: Optional[int] = None,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        duration: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        round: bool = False,
        supports_streaming: bool = False,
        muted: bool = False,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
    ) -> None:
        """
        Add a video to the album.

        :param file:
            The video to attach to the album.

            This behaves the same way as the file parameter in :meth:`telethon.Client.send_file`,
            *except* that it cannot be previously-sent media.

        :param size: See :meth:`telethon.Client.send_file`.
        :param name: See :meth:`telethon.Client.send_file`.
        :param mime_type: See :meth:`telethon.Client.send_file`.
        :param duration: See :meth:`telethon.Client.send_file`.
        :param width: See :meth:`telethon.Client.send_file`.
        :param height: See :meth:`telethon.Client.send_file`.
        :param round: See :meth:`telethon.Client.send_file`.
        :param supports_streaming: See :meth:`telethon.Client.send_file`.
        :param muted: See :meth:`telethon.Client.send_file`.
        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.
        """

        input_media: abcs.InputMedia
        if try_get_url_path(file) is not None:
            assert isinstance(file, str)
            input_media = types.InputMediaDocumentExternal(
                spoiler=False, url=file, ttl_seconds=None
            )
        else:
            input_file, name = await self._client._upload(file, size, name)
            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(name, strict=False)
                if mime_type is None:
                    mime_type = "application/octet-stream"

            attributes: list[abcs.DocumentAttribute] = []
            attributes.append(types.DocumentAttributeFilename(file_name=name))
            if duration is not None and width is not None and height is not None:
                attributes.append(
                    types.DocumentAttributeVideo(
                        round_message=round,
                        supports_streaming=supports_streaming,
                        nosound=muted,
                        duration=duration,
                        w=width,
                        h=height,
                        preload_prefix_size=None,
                    )
                )
            input_media = types.InputMediaUploadedDocument(
                nosound_video=muted,
                force_file=False,
                spoiler=False,
                file=input_file,
                thumb=None,
                mime_type=mime_type,
                attributes=attributes,
                stickers=None,
                ttl_seconds=None,
            )

        media = await self._client(
            functions.messages.upload_media(
                peer=types.InputPeerEmpty(), media=input_media
            )
        )
        assert isinstance(media, types.MessageMediaDocument)
        assert isinstance(media.document, types.Document)
        input_media = types.InputMediaDocument(
            spoiler=media.spoiler,
            id=types.InputDocument(
                id=media.document.id,
                access_hash=media.document.access_hash,
                file_reference=media.document.file_reference,
            ),
            ttl_seconds=media.ttl_seconds,
            query=None,
        )
        message, entities = parse_message(
            text=caption, markdown=caption_markdown, html=caption_html, allow_empty=True
        )
        self._medias.append(
            types.InputSingleMedia(
                media=input_media,
                random_id=generate_random_id(),
                message=message,
                entities=entities,
            )
        )

    async def send(
        self, peer: Peer | PeerRef, *, reply_to: Optional[int] = None
    ) -> list[Message]:
        """
        Send the album.

        :return: All sent messages that are part of the album.

        .. rubric:: Example

        .. code-block:: python

            album = await client.prepare_album()
            for photo in ('a.jpg', 'b.png'):
                await album.add_photo(photo)

            messages = await album.send(chat)
        """
        msg_map = self._client._build_message_map(
            await self._client(
                functions.messages.send_multi_media(
                    silent=False,
                    background=False,
                    clear_draft=False,
                    noforwards=False,
                    update_stickersets_order=False,
                    peer=peer._ref._to_input_peer(),
                    reply_to=(
                        types.InputReplyToMessage(
                            reply_to_msg_id=reply_to, top_msg_id=None
                        )
                        if reply_to
                        else None
                    ),
                    multi_media=self._medias,
                    schedule_date=None,
                    send_as=None,
                )
            ),
            peer._ref,
        )
        return [msg_map.with_random_id(media.random_id) for media in self._medias]
