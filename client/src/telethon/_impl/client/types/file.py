from __future__ import annotations

import mimetypes
import os
from inspect import isawaitable
from io import BufferedReader, BufferedWriter
from mimetypes import guess_type
from pathlib import Path
from typing import TYPE_CHECKING, Any, Coroutine, List, Optional, Protocol, Self, Union

from ...tl import abcs, types
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client import Client

math_round = round


def photo_size_byte_count(size: abcs.PhotoSize) -> int:
    if isinstance(size, types.PhotoCachedSize):
        return len(size.bytes)
    elif isinstance(size, types.PhotoPathSize):
        return len(size.bytes)
    elif isinstance(size, types.PhotoSize):
        return size.size
    elif isinstance(size, types.PhotoSizeEmpty):
        return 0
    elif isinstance(size, types.PhotoSizeProgressive):
        return max(size.sizes)
    elif isinstance(size, types.PhotoStrippedSize):
        return (
            len(stripped_size_header)
            + (len(size.bytes) - 3)
            + len(stripped_size_footer)
        )
    else:
        raise RuntimeError("unexpected case")


stripped_size_header = bytes.fromhex(
    "FFD8FFE000104A46494600010100000100010000FFDB004300281C1E231E19282321232D2B28303C64413C37373C7B585D4964918099968F808C8AA0B4E6C3A0AADAAD8A8CC8FFCBDAEEF5FFFFFF9BC1FFFFFFFAFFE6FDFFF8FFDB0043012B2D2D3C353C76414176F8A58CA5F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8F8FFC0001108001E002803012200021101031101FFC4001F0000010501010101010100000000000000000102030405060708090A0BFFC400B5100002010303020403050504040000017D01020300041105122131410613516107227114328191A1082342B1C11552D1F02433627282090A161718191A25262728292A3435363738393A434445464748494A535455565758595A636465666768696A737475767778797A838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE1E2E3E4E5E6E7E8E9EAF1F2F3F4F5F6F7F8F9FAFFC4001F0100030101010101010101010000000000000102030405060708090A0BFFC400B51100020102040403040705040400010277000102031104052131061241510761711322328108144291A1B1C109233352F0156272D10A162434E125F11718191A262728292A35363738393A434445464748494A535455565758595A636465666768696A737475767778797A82838485868788898A92939495969798999AA2A3A4A5A6A7A8A9AAB2B3B4B5B6B7B8B9BAC2C3C4C5C6C7C8C9CAD2D3D4D5D6D7D8D9DAE2E3E4E5E6E7E8E9EAF2F3F4F5F6F7F8F9FAFFDA000C03010002110311003F00"
)
stripped_size_footer = bytes.fromhex("FFD9")


def expand_stripped_size(data: bytes) -> bytearray:
    header = bytearray(stripped_size_header)
    header[164] = data[1]
    header[166] = data[2]
    return bytes(header) + data[3:] + stripped_size_footer


def photo_size_dimensions(
    size: abcs.PhotoSize,
) -> Optional[types.DocumentAttributeImageSize]:
    if isinstance(size, types.PhotoCachedSize):
        return types.DocumentAttributeImageSize(w=size.w, h=size.h)
    elif isinstance(size, types.PhotoPathSize):
        return None
    elif isinstance(size, types.PhotoSize):
        return types.DocumentAttributeImageSize(w=size.w, h=size.h)
    elif isinstance(size, types.PhotoSizeEmpty):
        return None
    elif isinstance(size, types.PhotoSizeProgressive):
        return types.DocumentAttributeImageSize(w=size.w, h=size.h)
    elif isinstance(size, types.PhotoStrippedSize):
        return types.DocumentAttributeImageSize(w=size.bytes[1], h=size.bytes[2])
    else:
        raise RuntimeError("unexpected case")


class InFileLike(Protocol):
    """
    A :term:`file-like object` used for input only.
    The :meth:`read` method can be :keyword:`async`.
    """

    def read(self, n: int) -> Union[bytes, Coroutine[Any, Any, bytes]]:
        pass


class OutFileLike(Protocol):
    """
    A :term:`file-like object` used for output only.
    The :meth:`write` method can be :keyword:`async`.
    """

    def write(self, data: bytes) -> Union[Any, Coroutine[Any, Any, Any]]:
        pass


class InWrapper:
    __slots__ = ("_fd", "_owned")

    def __init__(self, file: Union[str, Path, InFileLike]):
        if isinstance(file, str):
            file = Path(file)

        if isinstance(file, Path):
            self._fd: Union[InFileLike, BufferedReader] = file.open("rb")
            self._owned = True
        else:
            self._fd = file
            self._owned = False

    async def read(self, n: int) -> bytes:
        ret = self._fd.read(n)
        chunk = await ret if isawaitable(ret) else ret
        assert isinstance(chunk, bytes)
        return chunk

    def close(self) -> None:
        if self._owned:
            assert hasattr(self._fd, "close")
            self._fd.close()


class OutWrapper:
    __slots__ = ("_fd", "_owned")

    def __init__(self, file: Union[str, Path, OutFileLike]):
        if isinstance(file, str):
            file = Path(file)

        if isinstance(file, Path):
            self._fd: Union[OutFileLike, BufferedWriter] = file.open("wb")
            self._owned = True
        else:
            self._fd = file
            self._owned = False

    async def write(self, chunk: bytes) -> None:
        ret = self._fd.write(chunk)
        if isawaitable(ret):
            await ret

    def close(self) -> None:
        if self._owned:
            assert hasattr(self._fd, "close")
            self._fd.close()


class File(metaclass=NoPublicConstructor):
    """
    File information of uploaded media.

    It is used both when sending files or accessing media in a `Message`.
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
        thumb: Optional[abcs.PhotoSize],
        thumbs: Optional[List[abcs.PhotoSize]],
        raw: Optional[Union[abcs.MessageMedia, abcs.Photo, abcs.Document]],
        client: Optional[Client],
    ):
        self._path = path
        self._file = file
        self._attributes = attributes
        self._size = size
        self._name = name
        self._mime = mime
        self._photo = photo
        self._muted = muted
        self._input_media = input_media
        self._thumb = thumb
        self._thumbs = thumbs
        self._raw = raw
        self._client = client

    @classmethod
    def _try_from_raw_message_media(
        cls, client: Client, raw: abcs.MessageMedia
    ) -> Optional[Self]:
        if isinstance(raw, types.MessageMediaDocument):
            if raw.document:
                return cls._try_from_raw_document(
                    client,
                    raw.document,
                    spoiler=raw.spoiler,
                    ttl_seconds=raw.ttl_seconds,
                    orig_raw=raw,
                )
        elif isinstance(raw, types.MessageMediaPhoto):
            if raw.photo:
                return cls._try_from_raw_photo(
                    client,
                    raw.photo,
                    spoiler=raw.spoiler,
                    ttl_seconds=raw.ttl_seconds,
                    orig_raw=raw,
                )
        elif isinstance(raw, types.MessageMediaWebPage):
            if isinstance(raw.webpage, types.WebPage):
                if raw.webpage.document:
                    return cls._try_from_raw_document(
                        client, raw.webpage.document, orig_raw=raw
                    )
                if raw.webpage.photo:
                    return cls._try_from_raw_photo(
                        client, raw.webpage.photo, orig_raw=raw
                    )

        return None

    @classmethod
    def _try_from_raw_document(
        cls,
        client: Client,
        raw: abcs.Document,
        *,
        spoiler: bool = False,
        ttl_seconds: Optional[int] = None,
        orig_raw: Optional[abcs.MessageMedia] = None,
    ) -> Optional[Self]:
        if isinstance(raw, types.Document):
            return cls._create(
                path=None,
                file=None,
                attributes=raw.attributes,
                size=raw.size,
                name=next(
                    (
                        a.file_name
                        for a in raw.attributes
                        if isinstance(a, types.DocumentAttributeFilename)
                    ),
                    "",
                ),
                mime=raw.mime_type,
                photo=False,
                muted=next(
                    (
                        a.nosound
                        for a in raw.attributes
                        if isinstance(a, types.DocumentAttributeVideo)
                    ),
                    False,
                ),
                input_media=types.InputMediaDocument(
                    spoiler=spoiler,
                    id=types.InputDocument(
                        id=raw.id,
                        access_hash=raw.access_hash,
                        file_reference=raw.file_reference,
                    ),
                    ttl_seconds=ttl_seconds,
                    query=None,
                ),
                thumb=None,
                thumbs=raw.thumbs,
                raw=orig_raw or raw,
                client=client,
            )

        return None

    @classmethod
    def _try_from_raw_photo(
        cls,
        client: Client,
        raw: abcs.Photo,
        *,
        spoiler: bool = False,
        ttl_seconds: Optional[int] = None,
        orig_raw: Optional[abcs.MessageMedia] = None,
    ) -> Optional[Self]:
        if isinstance(raw, types.Photo):
            largest_thumb = max(raw.sizes, key=photo_size_byte_count)
            return cls._create(
                path=None,
                file=None,
                attributes=[],
                size=photo_size_byte_count(largest_thumb),
                name="",
                mime="image/jpeg",
                photo=True,
                muted=False,
                input_media=types.InputMediaPhoto(
                    spoiler=spoiler,
                    id=types.InputPhoto(
                        id=raw.id,
                        access_hash=raw.access_hash,
                        file_reference=raw.file_reference,
                    ),
                    ttl_seconds=ttl_seconds,
                ),
                thumb=largest_thumb,
                thumbs=[t for t in raw.sizes if t is not largest_thumb],
                raw=orig_raw or raw,
                client=client,
            )

        return None

    @classmethod
    def new(
        cls,
        path: Optional[Union[str, Path, Self]] = None,
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
    ) -> Self:
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
        if isinstance(path, cls):
            return path
        assert not isinstance(path, File)

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
                        nosound=muted,
                        duration=int(math_round(duration)),
                        w=width,
                        h=height,
                        preload_prefix_size=None,
                    )
                )

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

        return cls._create(
            path=Path(path) if path is not None else None,
            file=file,
            attributes=attributes,
            size=size,
            name=name,
            mime=mime_type,
            photo=photo,
            muted=muted,
            input_media=input_media,
            thumb=None,
            thumbs=None,
            raw=None,
            client=None,
        )

    @property
    def ext(self) -> str:
        """
        The file extension, including the leading dot ``.``.

        If the file does not represent and local file, the mimetype is used in :meth:`mimetypes.guess_extension`.

        If no extension is known for the mimetype, the empty string will be returned.
        This makes it safe to always append this property to a file name.
        """
        if self._path:
            return self._path.suffix
        else:
            return mimetypes.guess_extension(self._mime) or ""

    @property
    def thumbnails(self) -> List[File]:
        """
        The file thumbnails.

        For photos, these are often downscaled versions of the original size.

        For documents, these will be the thumbnails present in the document.
        """
        return [
            File._create(
                path=None,
                file=None,
                attributes=[],
                size=photo_size_byte_count(t),
                name="",
                mime="image/jpeg",
                photo=True,
                muted=False,
                input_media=self._input_media,
                thumb=t,
                thumbs=None,
                raw=self._raw,
                client=self._client,
            )
            for t in (self._thumbs or [])
        ]

    @property
    def width(self) -> Optional[int]:
        """
        The width of the image or video, if available.
        """
        if self._thumb and (dim := photo_size_dimensions(self._thumb)):
            return dim.w

        for attr in self._attributes:
            if isinstance(
                attr, (types.DocumentAttributeImageSize, types.DocumentAttributeVideo)
            ):
                return attr.w

        return None

    @property
    def height(self) -> Optional[int]:
        """
        The width of the image or video, if available.
        """
        if self._thumb and (dim := photo_size_dimensions(self._thumb)):
            return dim.h

        for attr in self._attributes:
            if isinstance(
                attr, (types.DocumentAttributeImageSize, types.DocumentAttributeVideo)
            ):
                return attr.h

        return None

    async def download(self, file: Union[str, Path, OutFileLike]) -> None:
        """
        Alias for :meth:`telethon.Client.download`.

        The file must have been obtained from Telegram to be downloadable.
        This means you cannot create local files, or files with an URL, and download them.

        See the documentation of :meth:`~telethon.Client.download` for an explanation of the parameters.
        """
        if not self._client:
            raise ValueError("only files from Telegram can be downloaded")

        await self._client.download(self, file)

    def _open(self) -> InWrapper:
        file = self._file or self._path
        if file is None:
            raise TypeError(f"cannot use file for uploading: {self}")
        return InWrapper(file)

    def _input_location(self) -> abcs.InputFileLocation:
        thumb_types = (
            types.PhotoSizeEmpty,
            types.PhotoSize,
            types.PhotoCachedSize,
            types.PhotoStrippedSize,
            types.PhotoSizeProgressive,
            types.PhotoPathSize,
        )
        if isinstance(self._input_media, types.InputMediaDocument):
            assert isinstance(self._input_media.id, types.InputDocument)
            return types.InputDocumentFileLocation(
                id=self._input_media.id.id,
                access_hash=self._input_media.id.access_hash,
                file_reference=self._input_media.id.file_reference,
                thumb_size=self._thumb.type
                if isinstance(self._thumb, thumb_types)
                else "",
            )
        elif isinstance(self._input_media, types.InputMediaPhoto):
            assert isinstance(self._input_media.id, types.InputPhoto)
            assert isinstance(self._thumb, thumb_types)

            return types.InputPhotoFileLocation(
                id=self._input_media.id.id,
                access_hash=self._input_media.id.access_hash,
                file_reference=self._input_media.id.file_reference,
                thumb_size=self._thumb.type,
            )
        else:
            raise TypeError(f"cannot use file for downloading: {self}")
