from typing import Self

from telethon._impl.tl import abcs

from .meta import NoPublicConstructor


class Message(metaclass=NoPublicConstructor):
    __slots__ = ("_message",)

    def __init__(self, message: abcs.Message) -> None:
        self._message = message

    @classmethod
    def _from_raw(cls, message: abcs.Message) -> Self:
        return cls._create(message)
