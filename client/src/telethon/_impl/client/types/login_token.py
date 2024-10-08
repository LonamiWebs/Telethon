from typing import Optional

from typing_extensions import Self

from ...tl import types
from .meta import NoPublicConstructor


class LoginToken(metaclass=NoPublicConstructor):
    """
    Result of requesting a login code via :meth:`telethon.Client.request_login_code`.
    """

    __slots__ = ("_code", "_phone")

    def __init__(self, code: types.auth.SentCode, phone: str) -> None:
        self._code = code
        self._phone = phone

    @classmethod
    def _new(cls, code: types.auth.SentCode, phone: str) -> Self:
        return cls._create(code, phone)

    @property
    def timeout(self) -> Optional[int]:
        """
        Number of seconds before this token expires.

        This property does not return different values as the current time advances.
        To determine when the token expires, add the timeout to the current time as soon as the token is obtained.
        """
        return self._code.timeout
