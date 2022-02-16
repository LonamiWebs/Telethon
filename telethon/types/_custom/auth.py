import asyncio
import re
from enum import Enum, auto
from ... import _tl


class CodeType(Enum):
    """
    The type of the login code sent.

    When resending the code, it won't be APP a second time.
    """

    APP = auto()
    SMS = auto()
    CALL = auto()
    FLASH_CALL = auto()
    MISSED_CALL = auto()


class SentCode:
    """
    Information about the login code request, returned by `client.send_code_request`.
    """

    @classmethod
    def _new(cls, code):
        self = cls.__new__(cls)
        self._code = code
        self._start = asyncio.get_running_loop().time()
        return self

    @property
    def type(self):
        """
        The `CodeType` which was sent.
        """
        return {
            _tl.auth.SentCodeTypeApp: CodeType.APP,
            _tl.auth.SentCodeTypeSms: CodeType.SMS,
            _tl.auth.SentCodeTypeCall: CodeType.CALL,
            _tl.auth.SentCodeTypeFlashCall: CodeType.FLASH_CALL,
            _tl.auth.SentCodeTypeMissedCall: CodeType.MISSED_CALL,
        }[type(self._code.type)]

    @property
    def next_type(self):
        """
        The `CodeType` which will be sent if `client.send_code_request`
        is used again after `timeout` seconds have elapsed. It may be `None`.
        """
        if not self._code.next_type:
            return None

        return {
            _tl.auth.CodeTypeSms: CodeType.SMS,
            _tl.auth.CodeTypeCall: CodeType.CALL,
            _tl.auth.CodeTypeFlashCall: CodeType.FLASH_CALL,
            _tl.auth.CodeTypeMissedCall: CodeType.MISSED_CALL,
        }[type(self._code.next_type)]

    @property
    def timeout(self):
        """
        How many seconds are left before `client.send_code_request` can be used to resend the code.
        Resending the code before this many seconds have elapsed may or may not work.

        This value can be `None`.

        This value is a positive floating point number, and is monotically decreasing.
        The value will reach zero after enough seconds have elapsed. This lets you do some work
        and call sleep on the value and still wait just long enough.

        If you need the original timeout, call `round` on the value as soon as possible.
        """
        if not self._code.timeout:
            return None

        return max(0.0, (self._start + self._code.timeout) - asyncio.get_running_loop().time())

    @property
    def length(self):
        """
        The length of the sent code.

        If the length is unknown (it could be any length), `None` is returned.
        This can be true for `CodeType.FLASH_CALL`.
        """
        if isinstance(self._code.type, _tl.auth.SentCodeTypeFlashCall):
            return None if self._code.type.pattern in ('', '*') else len(self._code.type.pattern)
        else:
            return self._code.type.length

    def check(self, code):
        """
        Check if the user's input code is valid.

        This can be used to implement a client-side validation before actually trying to login
        (mostly useful with a graphic interface, to hint the user the code is not yet correct).
        """
        if not isinstance(code, str):
            raise TypeError(f'code must be str, but was {type(code)}')

        if isinstance(self._code.type, _tl.auth.SentCodeTypeFlashCall):
            if self._code.type.pattern in ('', '*'):
                return True

            if not all(c.isdigit() or c == '*' for c in self._code.type.pattern):
                # Potentially unsafe to use this pattern in a regex
                raise RuntimeError(f'Unrecognised code pattern: {self._code.type.pattern!r}')

            pattern = self._code.type.pattern.replace('*', r'\d*')
            numbers = ''.join(c for c in code if c.isdigit())
            return re.match(f'^{pattern}$', numbers) is not None

        if isinstance(self._code.type, _tl.auth.SentCodeTypeMissedCall):
            if not code.startswith(self._code.type.prefix):
                return False

        return len(code) == self._code.type.length
