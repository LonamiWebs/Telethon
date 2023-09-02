from __future__ import annotations

import hashlib
import os
from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Coroutine, List, Optional, Protocol, Self, Union

from ...tl import abcs, functions, types
from ..types import ChatLike, Message, NoPublicConstructor
from ..utils import generate_random_id
from .messages import parse_message

if TYPE_CHECKING:
    from .client import Client


MIN_CHUNK_SIZE = 4 * 1024
MAX_CHUNK_SIZE = 512 * 1024
FILE_MIGRATE_ERROR = 303
BIG_FILE_SIZE = 10 * 1024 * 1024

math_round = round


class InFileLike(Protocol):
    """
    [File-like object](https://docs.python.org/3/glossary.html#term-file-like-object)
    used for input only, where the `read` method can be `async`.
    """

    def read(self, n: int) -> Union[bytes, Coroutine[Any, Any, bytes]]:
        pass


class OutFileLike(Protocol):
    """
    [File-like object](https://docs.python.org/3/glossary.html#term-file-like-object)
    used for output only, where the `write` method can be `async`.
    """

    def write(self, data: bytes) -> Union[Any, Coroutine[Any, Any, Any]]:
        pass


MediaLike = object


class File(metaclass=NoPublicConstructor):
    """
    File information of uploaded media.
    """

    def __init__(
        self,
        *,
        path: Optional[Path],
        file: Optional[InFileLike],
        attributes: List[abcs.DocumentAttribute],
        size: int,
        name: str,
        mime: str,
        photo: bool,
        muted: bool,
        input_media: Optional[abcs.InputMedia],
    ):
        self._path = path
        self._file = file
        self._attributes = attributes
        self._size = size
        self._name = name
        self._mime = mime
        self._photo = photo
        self._muted = muted
        self._input_file: Optional[abcs.InputFile] = None
        self._input_media: Optional[abcs.InputMedia] = input_media

    @classmethod
    def new(
        cls,
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
    ) -> "File":
        """
        Create file information that can later be sent as media.

        If the path is a `File`, the rest of parameters are ignored, and
        this existing instance is returned instead (the method is a no-op).

        Only one of path, url or file must be specified.

        If a local file path is not given, size and name must be specified.

        The mime_type will be inferred from the name if it is omitted.

        The rest of parameters are only used depending on the mime_type:

        * For image/:
        * width (required), in pixels, of the media.
        * height (required), in pixels, of the media.
        * For audio/:
        * duration (required), in seconds, of the media. This will be rounded.
        * voice, if it's a live recording.
        * title, of the song.
        * performer, with the name of the artist.
        * For video/:
        * duration (required), in seconds, of the media. This will be rounded.
        * width (required), in pixels, of the media.
        * height (required), in pixels, of the media.
        * round, if it should be displayed as a round video.
        * supports_streaming, if clients are able to stream the video.
        * muted, if the sound from the video is or should be missing.
        * For sticker:
        * animated, if it's not a static image.
        * emoji, as the alternative text for the sticker.
        * stickerset, to which the sticker belongs.

        If any of the required fields are missing, the attribute will not be sent.
        """
        if isinstance(path, File):
            return path

        attributes: List[abcs.DocumentAttribute] = []

        if sum((path is not None, url is not None, file is not None)) != 1:
            raise ValueError("must specify exactly one of path, markdown or html")

        if path is not None:
            size = os.path.getsize(path)
            name = os.path.basename(path)

        if size is None:
            raise ValueError("must specify size")
        if name is None:
            raise ValueError("must specify name")

        if mime_type is None:
            mime_type, _ = guess_type(name, strict=False)
        if mime_type is None:
            raise ValueError("must specify mime_type")

        if sum((path is not None, url is not None, file is not None)) != 1:
            raise ValueError("must specify exactly one of path, markdown or html")

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
                        duration=int(math_round(duration)),
                        w=width,
                        h=height,
                    )
                )
        else:
            raise NotImplementedError("sticker")

        photo = compress and mime_type.startswith("image/")

        input_media: Optional[abcs.InputMedia]
        if url is not None:
            if photo:
                input_media = types.InputMediaPhotoExternal(
                    spoiler=False, url=url, ttl_seconds=None
                )
            else:
                input_media = types.InputMediaDocumentExternal(
                    spoiler=False, url=url, ttl_seconds=None
                )
        else:
            input_media = None

        return cls(
            path=Path(path) if path is not None else None,
            file=file,
            attributes=attributes,
            size=size,
            name=name,
            mime=mime_type,
            photo=photo,
            muted=muted,
            input_media=input_media,
        )

    async def _read(self, n: int) -> bytes:
        raise NotImplementedError


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
                reply_to_msg_id=None,
                top_msg_id=None,
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
    pass
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
    pass
