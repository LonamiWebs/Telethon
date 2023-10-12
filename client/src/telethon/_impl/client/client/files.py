from __future__ import annotations

import hashlib
import mimetypes
import urllib.parse
from inspect import isawaitable
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

from ...tl import abcs, functions, types
from ..types import (
    AsyncList,
    ChatLike,
    File,
    InFileLike,
    Message,
    OutFileLike,
    OutWrapper,
)
from ..types.file import expand_stripped_size
from ..utils import generate_random_id
from .messages import parse_message

if TYPE_CHECKING:
    from .client import Client


MIN_CHUNK_SIZE = 4 * 1024
MAX_CHUNK_SIZE = 512 * 1024
FILE_MIGRATE_ERROR = 303
BIG_FILE_SIZE = 10 * 1024 * 1024

# ``round`` parameter would make this more annoying to access otherwise.
math_round = round


async def send_photo(
    self: Client,
    chat: ChatLike,
    file: Union[str, Path, InFileLike, File],
    *,
    size: Optional[int] = None,
    name: Optional[str] = None,
    compress: bool = True,
    width: Optional[int] = None,
    height: Optional[int] = None,
    caption: Optional[str] = None,
    caption_markdown: Optional[str] = None,
    caption_html: Optional[str] = None,
) -> Message:
    return await send_file(
        self,
        chat,
        file,
        size=size,
        name=name,
        compress=compress,
        width=width,
        height=height,
        caption=caption,
        caption_markdown=caption_markdown,
        caption_html=caption_html,
    )


async def send_audio(
    self: Client,
    chat: ChatLike,
    file: Union[str, Path, InFileLike, File],
    *,
    size: Optional[int] = None,
    name: Optional[str] = None,
    duration: Optional[float] = None,
    voice: bool = False,
    title: Optional[str] = None,
    performer: Optional[str] = None,
    caption: Optional[str] = None,
    caption_markdown: Optional[str] = None,
    caption_html: Optional[str] = None,
) -> Message:
    return await send_file(
        self,
        chat,
        file,
        size=size,
        name=name,
        duration=duration,
        voice=voice,
        title=title,
        performer=performer,
        caption=caption,
        caption_markdown=caption_markdown,
        caption_html=caption_html,
    )


async def send_video(
    self: Client,
    chat: ChatLike,
    file: Union[str, Path, InFileLike, File],
    *,
    size: Optional[int] = None,
    name: Optional[str] = None,
    duration: Optional[float] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    round: bool = False,
    supports_streaming: bool = False,
    caption: Optional[str] = None,
    caption_markdown: Optional[str] = None,
    caption_html: Optional[str] = None,
) -> Message:
    return await send_file(
        self,
        chat,
        file,
        size=size,
        name=name,
        duration=duration,
        width=width,
        height=height,
        round=round,
        supports_streaming=supports_streaming,
        caption=caption,
        caption_markdown=caption_markdown,
        caption_html=caption_html,
    )


def try_get_url_path(maybe_url: Union[str, Path, InFileLike]) -> Optional[str]:
    if not isinstance(maybe_url, str):
        return None
    lowercase = maybe_url.lower()
    if lowercase.startswith("http://") or lowercase.startswith("https://"):
        return urllib.parse.urlparse(maybe_url).path
    return None


async def send_file(
    self: Client,
    chat: ChatLike,
    file: Union[str, Path, InFileLike, File],
    *,
    size: Optional[int] = None,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
    compress: bool = False,
    animated: bool = False,
    duration: Optional[float] = None,
    voice: bool = False,
    title: Optional[str] = None,
    performer: Optional[str] = None,
    emoji: Optional[str] = None,
    emoji_sticker: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    round: bool = False,
    supports_streaming: bool = False,
    muted: bool = False,
    caption: Optional[str] = None,
    caption_markdown: Optional[str] = None,
    caption_html: Optional[str] = None,
) -> Message:
    message, entities = parse_message(
        text=caption, markdown=caption_markdown, html=caption_html, allow_empty=True
    )
    assert isinstance(message, str)

    # Re-send existing file.
    if isinstance(file, File):
        return await do_send_file(self, chat, file._input_media, message, entities)

    # URLs are handled early as they can't use any other attributes either.
    input_media: abcs.InputMedia
    if (url_path := try_get_url_path(file)) is not None:
        assert isinstance(file, str)
        if compress:
            if mime_type is None:
                if name is None:
                    name = Path(url_path).name
                mime_type, _ = mimetypes.guess_type(name, strict=False)
            as_photo = mime_type and mime_type.startswith("image/")
        else:
            as_photo = False
        if as_photo:
            input_media = types.InputMediaPhotoExternal(
                spoiler=False, url=file, ttl_seconds=None
            )
        else:
            input_media = types.InputMediaDocumentExternal(
                spoiler=False, url=file, ttl_seconds=None
            )
        return await do_send_file(self, chat, input_media, message, entities)

    # Paths are opened and closed by us. Anything else is *only* read, not closed.
    if isinstance(file, (str, Path)):
        path = Path(file) if isinstance(file, str) else file
        if size is None:
            size = path.stat().st_size
        if name is None:
            name = path.name
        with path.open("rb") as fd:
            input_file = await upload(self, fd, size, name)
    else:
        if size is None:
            raise ValueError("size must be set when sending file-like objects")
        if name is None:
            raise ValueError("name must be set when sending file-like objects")
        input_file = await upload(self, file, size, name)

    # Mime is mandatory for documents, but we also use it to determine whether to send as photo.
    if mime_type is None:
        mime_type, _ = mimetypes.guess_type(name, strict=False)
        if mime_type is None:
            mime_type = "application/octet-stream"

    as_photo = compress and mime_type.startswith("image/")
    if as_photo:
        input_media = types.InputMediaUploadedPhoto(
            spoiler=False,
            file=input_file,
            stickers=None,
            ttl_seconds=None,
        )

    # Only bother to calculate attributes when sending documents.
    else:
        attributes: List[abcs.DocumentAttribute] = []
        attributes.append(types.DocumentAttributeFilename(file_name=name))

        if mime_type.startswith("image/"):
            if width is not None and height is not None:
                attributes.append(types.DocumentAttributeImageSize(w=width, h=height))
        elif mime_type.startswith("audio/"):
            if duration is not None:
                attributes.append(
                    types.DocumentAttributeAudio(
                        voice=voice,
                        duration=int(math_round(duration)),
                        title=title,
                        performer=performer,
                        waveform=None,
                    )
                )
        elif mime_type.startswith("video/"):
            if duration is not None and width is not None and height is not None:
                attributes.append(
                    types.DocumentAttributeVideo(
                        round_message=round,
                        supports_streaming=supports_streaming,
                        nosound=muted,
                        duration=int(math_round(duration)),
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

    return await do_send_file(self, chat, input_media, message, entities)


async def do_send_file(
    client: Client,
    chat: ChatLike,
    input_media: abcs.InputMedia,
    message: str,
    entities: Optional[List[abcs.MessageEntity]],
) -> Message:
    peer = (await client._resolve_to_packed(chat))._to_input_peer()
    random_id = generate_random_id()
    return client._build_message_map(
        await client(
            functions.messages.send_media(
                silent=False,
                background=False,
                clear_draft=False,
                noforwards=False,
                update_stickersets_order=False,
                peer=peer,
                reply_to=None,
                media=input_media,
                message=message,
                random_id=random_id,
                reply_markup=None,
                entities=entities,
                schedule_date=None,
                send_as=None,
            )
        ),
        peer,
    ).with_random_id(random_id)


async def upload(
    client: Client,
    fd: InFileLike,
    size: int,
    name: str,
) -> abcs.InputFile:
    file_id = generate_random_id()

    uploaded = 0
    part = 0
    total_parts = (size + MAX_CHUNK_SIZE - 1) // MAX_CHUNK_SIZE
    buffer = bytearray()
    to_store: Union[bytearray, bytes] = b""
    hash_md5 = hashlib.md5()
    is_big = size > BIG_FILE_SIZE

    while uploaded != size:
        ret = fd.read(MAX_CHUNK_SIZE - len(buffer))
        chunk = await ret if isawaitable(ret) else ret
        assert isinstance(chunk, bytes)
        if not chunk:
            raise ValueError("unexpected end-of-file")

        if len(chunk) == MAX_CHUNK_SIZE or uploaded + len(chunk) == size:
            to_store = chunk
        else:
            buffer += chunk
            if len(buffer) == MAX_CHUNK_SIZE:
                to_store = buffer
            else:
                continue

        if is_big:
            await client(
                functions.upload.save_big_file_part(
                    file_id=file_id,
                    file_part=part,
                    file_total_parts=part,
                    bytes=to_store,
                )
            )
        else:
            await client(
                functions.upload.save_file_part(
                    file_id=file_id, file_part=total_parts, bytes=to_store
                )
            )
            hash_md5.update(to_store)

        buffer.clear()
        part += 1

    if is_big:
        return types.InputFileBig(
            id=file_id,
            parts=total_parts,
            name=name,
        )
    else:
        return types.InputFile(
            id=file_id,
            parts=total_parts,
            name=name,
            md5_checksum=hash_md5.hexdigest(),
        )


class FileBytesList(AsyncList[bytes]):
    def __init__(
        self,
        client: Client,
        file: File,
    ):
        super().__init__()
        self._client = client
        self._loc = file._input_location()
        self._offset = 0
        if isinstance(file._thumb, types.PhotoStrippedSize):
            self._buffer.append(expand_stripped_size(file._thumb.bytes))
            self._done = True

    async def _fetch_next(self) -> None:
        result = await self._client(
            functions.upload.get_file(
                precise=False,
                cdn_supported=False,
                location=self._loc,
                offset=self._offset,
                limit=MAX_CHUNK_SIZE,
            )
        )
        assert isinstance(result, types.upload.File)

        if result.bytes:
            self._offset += MAX_CHUNK_SIZE
            self._buffer.append(result.bytes)

        self._done = len(result.bytes) < MAX_CHUNK_SIZE


def get_file_bytes(self: Client, media: File) -> AsyncList[bytes]:
    return FileBytesList(self, media)


async def download(
    self: Client, media: File, file: Union[str, Path, OutFileLike]
) -> None:
    fd = OutWrapper(file)
    try:
        async for chunk in get_file_bytes(self, media):
            ret = fd.write(chunk)
            if isawaitable(ret):
                await ret

    finally:
        fd.close()
