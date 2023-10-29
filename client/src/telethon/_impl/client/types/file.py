from __future__ import annotations

import mimetypes
from inspect import isawaitable
from io import BufferedWriter
from pathlib import Path
from typing import TYPE_CHECKING, Any, Coroutine, List, Optional, Protocol, Self, Union

from ...tl import abcs, types
from .meta import NoPublicConstructor

if TYPE_CHECKING:
    from ..client.client import Client

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


def expand_stripped_size(data: bytes) -> bytes:
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

    This is never returned and should never be constructed.
    It's only used in function parameters.
    """

    def read(self, n: int) -> Union[bytes, Coroutine[Any, Any, bytes]]:
        """
        Read from the file or buffer.

        :param n:
            Maximum amount of bytes that should be returned.
        """


class OutFileLike(Protocol):
    """
    A :term:`file-like object` used for output only.
    The :meth:`write` method can be :keyword:`async`.

    This is never returned and should never be constructed.
    It's only used in function parameters.
    """

    def write(self, data: bytes) -> Union[Any, Coroutine[Any, Any, Any]]:
        """
        Write all the data into the file or buffer.

        :param data:
            Data that must be written to the buffer entirely.
        """


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
    File information of media sent to Telegram that can be downloaded.

    You can get a file from messages via :attr:`telethon.types.Message.file`,
    or from methods such as :meth:`telethon.Client.get_profile_photos`.
    """

    def __init__(
        self,
        *,
        attributes: List[abcs.DocumentAttribute],
        size: int,
        name: str,
        mime: str,
        photo: bool,
        muted: bool,
        input_media: abcs.InputMedia,
        thumb: Optional[abcs.PhotoSize],
        thumbs: Optional[List[abcs.PhotoSize]],
        raw: Optional[Union[abcs.MessageMedia, abcs.Photo, abcs.Document]],
        client: Optional[Client],
    ):
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

    @property
    def name(self) -> Optional[str]:
        """
        The file name, if known.
        """
        for attr in self._attributes:
            if isinstance(attr, types.DocumentAttributeFilename):
                return attr.file_name

        return None

    @property
    def ext(self) -> str:
        """
        The file extension, including the leading dot ``.``.

        If the name is not known, the mime-type is used in :func:`mimetypes.guess_extension`.

        If no extension is known for the mime-type, the empty string will be returned.
        This makes it safe to always append this property to a file name.
        """
        if name := self._name:
            return Path(name).suffix
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

        :param file: See :meth:`~telethon.Client.download`.
        """
        if not self._client:
            raise ValueError("only files from Telegram can be downloaded")

        await self._client.download(self, file)

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
