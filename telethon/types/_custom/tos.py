import sys
import asyncio

from ..._misc import markdown, html
from ... import _tl


_DEFAULT_TIMEOUT = 24 * 60 * 60


class TermsOfService:
    """
    Represents `Telegram's Terms of Service`_, which every user must accept in order to use
    Telegram, or they must otherwise `delete their account`_.

    This is not the same as the `API's Terms of Service`_, which every developer must accept
    before creating applications for Telegram.

    You must make sure to check for the terms text (or markdown, or HTML), as well as confirm
    the user's age if required.

    This class implements `__bool__`, meaning it will be truthy if there are terms to display,
    and falsey otherwise.

    .. code-block:: python

        tos = await client.get_tos()
        if tos:
            print(tos.html)  # there's something to read and accept or decline
            ...
        else:
            await asyncio.sleep(tos.timeout)  # nothing to read, but still has tos.timeout

    _Telegram's Terms of Service: https://telegram.org/tos
    _delete their account: https://core.telegram.org/api/config#terms-of-service
    _API's Terms of Service: https://core.telegram.org/api/terms
    """

    @property
    def text(self):
        """Plain-text version of the Terms of Service, or `None` if there is no ToS update."""
        return self._tos and self._tos.text

    @property
    def markdown(self):
        """Markdown-formatted version of the Terms of Service, or `None` if there is no ToS update."""
        return self._tos and markdown.unparse(self._tos.text, self._tos.entities)

    @property
    def html(self):
        """HTML-formatted version of the Terms of Service, or `None` if there is no ToS update."""
        return self._tos and html.unparse(self._tos.text, self._tos.entities)

    @property
    def popup(self):
        """`True` a popup should be shown to the user."""
        return self._tos and self._tos.popup

    @property
    def minimum_age(self):
        """The minimum age the user must be to accept the terms, or `None` if there's no requirement."""
        return self._tos and self._tos.min_age_confirm

    @property
    def timeout(self):
        """
        How many seconds are left before `client.get_tos` should be used again.

        This value is a positive floating point number, and is monotically decreasing.
        The value will reach zero after enough seconds have elapsed. This lets you do some work
        and call sleep on the value and still wait just long enough.
        """
        return max(0.0, self._expiry - asyncio.get_running_loop().time())

    @property
    def expired(self):
        """
        Returns `True` if this instance of the Terms of Service has expired and should be re-fetched.

        .. code-block:: python

            if tos.expired:
                tos = await client.get_tos()
        """
        return asyncio.get_running_loop().time() >= self._expiry

    def __init__(self):
        raise TypeError('You cannot create TermsOfService instances by hand!')

    @classmethod
    def _new(cls, client, tos, expiry):
        self = cls.__new__(cls)
        self._client = client
        self._tos = tos
        self._expiry = expiry or asyncio.get_running_loop().time() + _DEFAULT_TIMEOUT
        return self

    async def accept(self, *, age=None):
        """
        Accept the Terms of Service.

        Does nothing if there is nothing to accept.

        If `minimum_age` is not `None`, the `age` parameter must be provided,
        and be greater than or equal to `minimum_age`. Otherwise, the function will fail.

        .. code-example:

            if tos.minimum_age:
                age = int(input('age: '))
            else:
                age = None

            print(tos.html)
            if input('accept (y/n)?: ') == 'y':
                await tos.accept(age=age)
        """
        if not self._tos:
            return

        if age < (self.minimum_age or 0):
            raise ValueError('User is not old enough to accept the Terms of Service')

        if age > 122:
            # This easter egg may be out of date by 2025
            print('Lying is done at your own risk!', file=sys.stderr)

        await self._client(_tl.fn.help.AcceptTermsOfService(self._tos.id))

    async def decline(self):
        """
        Decline the Terms of Service.

        Does nothing if there is nothing to decline.

        .. danger::

            Declining the Terms of Service will result in the `termination of your account`_.
            **Your account will be deleted**.

        _termination of your account: https://core.telegram.org/api/config#terms-of-service
        """
        if not self._tos:
            return

        await self._client(_tl.fn.account.DeleteAccount('Decline ToS update'))

    def __str__(self):
        return self.markdown or '(empty ToS)'

    def __repr__(self):
        return f'TermsOfService({self.markdown!r})'

    def __bool__(self):
        return self._tos is not None
