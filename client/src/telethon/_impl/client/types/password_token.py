from typing import Self

from ...tl import types
from .meta import NoPublicConstructor


class PasswordToken(metaclass=NoPublicConstructor):
    """
    Result of attempting to :meth:`~telethon.Client.sign_in` to a 2FA-protected account.
    """

    __slots__ = ("_password",)

    def __init__(self, password: types.account.Password) -> None:
        self._password = password

    @classmethod
    def _new(cls, password: types.account.Password) -> Self:
        return cls._create(password)

    @property
    def hint(self) -> str:
        """
        The password hint, or the empty string if none is known.
        """
        return self._password.hint or ""
