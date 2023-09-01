import datetime
from typing import Optional, Self

from ...client.types.chat import Chat
from ...tl import abcs, types
from .meta import NoPublicConstructor


class Message(metaclass=NoPublicConstructor):
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
