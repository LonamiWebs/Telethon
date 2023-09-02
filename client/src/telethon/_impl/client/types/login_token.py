from typing import Self

from ...tl import types
from .meta import NoPublicConstructor


class LoginToken(metaclass=NoPublicConstructor):
    __slots__ = ("_code", "_phone")

    def __init__(self, code: types.auth.SentCode, phone: str) -> None:
        self._code = code
        self._phone = phone

    @classmethod
    def _new(cls, code: types.auth.SentCode, phone: str) -> Self:
        return cls._create(code, phone)
