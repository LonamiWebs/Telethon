import os
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Coroutine, List, Optional, Protocol, Self, Union

from ...tl import abcs, types
from .meta import NoPublicConstructor

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
        if len(size.bytes) < 3 or size.bytes[0] != 1:
            return len(size.bytes)

        return len(size.bytes) + 622
    else:
        raise RuntimeError("unexpected case")


MediaLike = object


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
        raw: Optional[Union[types.MessageMediaDocument, types.MessageMediaPhoto]],
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
        self._raw = raw

    @classmethod
    def _try_from_raw(cls, raw: abcs.MessageMedia) -> Optional[Self]:
        if isinstance(raw, types.MessageMediaDocument):
            if isinstance(raw.document, types.Document):
                return cls._create(
                    path=None,
                    file=None,
                    attributes=raw.document.attributes,
                    size=raw.document.size,
                    name=next(
                        (
                            a.file_name
                            for a in raw.document.attributes
                            if isinstance(a, types.DocumentAttributeFilename)
                        ),
                        "",
                    ),
                    mime=raw.document.mime_type,
                    photo=False,
                    muted=next(
                        (
                            a.nosound
                            for a in raw.document.attributes
                            if isinstance(a, types.DocumentAttributeVideo)
                        ),
                        False,
                    ),
                    input_media=types.InputMediaDocument(
                        spoiler=raw.spoiler,
                        id=types.InputDocument(
                            id=raw.document.id,
                            access_hash=raw.document.access_hash,
                            file_reference=raw.document.file_reference,
                        ),
                        ttl_seconds=raw.ttl_seconds,
                        query=None,
                    ),
                    raw=raw,
                )
        elif isinstance(raw, types.MessageMediaPhoto):
            if isinstance(raw.photo, types.Photo):
                return cls._create(
                    path=None,
                    file=None,
                    attributes=[],
                    size=max(map(photo_size_byte_count, raw.photo.sizes)),
                    name="",
                    mime="image/jpeg",
                    photo=True,
                    muted=False,
                    input_media=types.InputMediaPhoto(
                        spoiler=raw.spoiler,
                        id=types.InputPhoto(
                            id=raw.photo.id,
                            access_hash=raw.photo.access_hash,
                            file_reference=raw.photo.file_reference,
                        ),
                        ttl_seconds=raw.ttl_seconds,
                    ),
                    raw=raw,
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
            raw=None,
        )

    async def _read(self, n: int) -> bytes:
        raise NotImplementedError
