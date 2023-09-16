from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from ...tl import abcs, functions, types
from ..types import ChatLike, File, InFileLike, MediaLike, Message, OutFileLike
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
        text=caption, markdown=caption_markdown, html=caption_html
    )

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

    while uploaded != file._size:
        chunk = await file._read(MAX_CHUNK_SIZE - len(buffer))
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

    if file._size > BIG_FILE_SIZE:
        types.InputFileBig(
            id=file_id,
            parts=total_parts,
            name=file._name,
        )
    else:
        types.InputFile(
            id=file_id,
            parts=total_parts,
            name=file._name,
            md5_checksum=hash_md5.hexdigest(),
        )
    raise NotImplementedError


async def iter_download(self: Client) -> None:
    raise NotImplementedError
    # result = self(
    #     functions.upload.get_file(
    #         precise=False,
    #         cdn_supported=False,
    #         location=types.InputFileLocation(),
    #         offset=0,
    #         limit=MAX_CHUNK_SIZE,
    #     )
    # )
    # assert isinstance(result, types.upload.File)
    # if len(result.bytes) < MAX_CHUNK_SIZE:
    #     done
    # else:
    #     offset += MAX_CHUNK_SIZE


async def download(self: Client, media: MediaLike, file: OutFileLike) -> None:
    raise NotImplementedError
