import datetime
from typing import Optional, Self

from ...tl import abcs, types
from .chat import Chat
from .file import File
from .meta import NoPublicConstructor


class Message(metaclass=NoPublicConstructor):
    """
    A sent message.
    """

    __slots__ = ("_raw",)

    def __init__(self, message: abcs.Message) -> None:
        assert isinstance(
            message, (types.Message, types.MessageService, types.MessageEmpty)
        )
        self._raw = message

    @classmethod
    def _from_raw(cls, message: abcs.Message) -> Self:
        return cls._create(message)

    @property
    def id(self) -> int:
        return self._raw.id

    @property
    def text(self) -> Optional[str]:
        return getattr(self._raw, "message", None)

    @property
    def text_html(self) -> Optional[str]:
        raise NotImplementedError

    @property
    def text_markdown(self) -> Optional[str]:
        raise NotImplementedError

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
        raise NotImplementedError

    @property
    def sender(self) -> Chat:
        raise NotImplementedError

    def _file(self) -> Optional[File]:
        return (
            File._try_from_raw(self._raw.media)
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

    async def delete(self) -> None:
        raise NotImplementedError

    async def edit(self) -> None:
        raise NotImplementedError

    async def forward_to(self) -> None:
        raise NotImplementedError
