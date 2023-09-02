from typing import Self

from ...tl import types
from .meta import NoPublicConstructor


class PasswordToken(metaclass=NoPublicConstructor):
    __slots__ = ("_password",)

    def __init__(self, password: types.account.Password) -> None:
        self._password = password

    @classmethod
    def _new(cls, password: types.account.Password) -> Self:
        return cls._create(password)

    @property
    def hint(self) -> str:
        return self._password.hint or ""
