from __future__ import annotations

import hashlib
from inspect import isawaitable
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

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


async def send_photo(
    self: Client,
    chat: ChatLike,
    path: Optional[Union[str, Path, File]] = None,
    *,
    url: Optional[str] = None,
    file: Optional[InFileLike] = None,
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
        path,
        url=url,
        file=file,
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
    path: Optional[Union[str, Path, File]] = None,
    *,
    url: Optional[str] = None,
    file: Optional[InFileLike] = None,
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
        path,
        url=url,
        file=file,
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
    path: Optional[Union[str, Path, File]] = None,
    *,
    url: Optional[str] = None,
    file: Optional[InFileLike] = None,
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
        path,
        url=url,
        file=file,
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


async def send_file(
    self: Client,
    chat: ChatLike,
    path: Optional[Union[str, Path, File]] = None,
    *,
    url: Optional[str] = None,
    file: Optional[InFileLike] = None,
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
    file_info = File.new(
        path,
        url=url,
        file=file,
        size=size,
        name=name,
        mime_type=mime_type,
        compress=compress,
        animated=animated,
        duration=duration,
        voice=voice,
        title=title,
        performer=performer,
        emoji=emoji,
        emoji_sticker=emoji_sticker,
        width=width,
        height=height,
        round=round,
        supports_streaming=supports_streaming,
        muted=muted,
    )
    message, entities = parse_message(
        text=caption, markdown=caption_markdown, html=caption_html, allow_empty=True
    )
    assert isinstance(message, str)

    peer = (await self._resolve_to_packed(chat))._to_input_peer()

    if file_info._input_media is None:
        if file_info._input_file is None:
            file_info._input_file = await upload(self, file_info)
        file_info._input_media = (
            types.InputMediaUploadedPhoto(
                spoiler=False,
                file=file_info._input_file,
                stickers=None,
                ttl_seconds=None,
            )
            if file_info._photo
            else types.InputMediaUploadedDocument(
                nosound_video=file_info._muted,
                force_file=False,
                spoiler=False,
                file=file_info._input_file,
                thumb=None,
                mime_type=file_info._mime,
                attributes=file_info._attributes,
                stickers=None,
                ttl_seconds=None,
            )
        )
    random_id = generate_random_id()

    return self._build_message_map(
        await self(
            functions.messages.send_media(
                silent=False,
                background=False,
                clear_draft=False,
                noforwards=False,
                update_stickersets_order=False,
                peer=peer,
                reply_to=None,
                media=file_info._input_media,
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
    file: File,
) -> abcs.InputFile:
    file_id = generate_random_id()

    uploaded = 0
    part = 0
    total_parts = (file._size + MAX_CHUNK_SIZE - 1) // MAX_CHUNK_SIZE
    buffer = bytearray()
    to_store: Union[bytearray, bytes] = b""
    hash_md5 = hashlib.md5()
    is_big = file._size > BIG_FILE_SIZE

    fd = file._open()
    try:
        while uploaded != file._size:
            chunk = await fd.read(MAX_CHUNK_SIZE - len(buffer))
            if not chunk:
                raise ValueError("unexpected end-of-file")

            if len(chunk) == MAX_CHUNK_SIZE or uploaded + len(chunk) == file._size:
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
    finally:
        fd.close()

    if file._size > BIG_FILE_SIZE:
        return types.InputFileBig(
            id=file_id,
            parts=total_parts,
            name=file._name,
        )
    else:
        return types.InputFile(
            id=file_id,
            parts=total_parts,
            name=file._name,
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
