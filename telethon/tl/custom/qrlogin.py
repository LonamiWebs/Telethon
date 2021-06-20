import asyncio
import base64
import datetime

from .. import types, functions
from ... import events


class QRLogin:
    """
    QR login information.

    Most of the time, you will present the `url` as a QR code to the user,
    and while it's being shown, call `wait`.
    """
    def __init__(self, client, ignored_ids):
        self._client = client
        self._request = functions.auth.ExportLoginTokenRequest(
            self._client.api_id, self._client.api_hash, ignored_ids)
        self._resp = None

    async def recreate(self):
        """
        Generates a new token and URL for a new QR code, useful if the code
        has expired before it was imported.
        """
        self._resp = await self._client(self._request)

    @property
    def token(self) -> bytes:
        """
        The binary data representing the token.

        It can be used by a previously-authorized client in a call to
        :tl:`auth.importLoginToken` to log the client that originally
        requested the QR login.
        """
        return self._resp.token

    @property
    def url(self) -> str:
        """
        The ``tg://login`` URI with the token. When opened by a Telegram
        application where the user is logged in, it will import the login
        token.

        If you want to display a QR code to the user, this is the URL that
        should be launched when the QR code is scanned (the URL that should
        be contained in the QR code image you generate).

        Whether you generate the QR code image or not is up to you, and the
        library can't do this for you due to the vast ways of generating and
        displaying the QR code that exist.

        The URL simply consists of `token` base64-encoded.
        """
        return 'tg://login?token={}'.format(base64.urlsafe_b64encode(self._resp.token).decode('utf-8').rstrip('='))

    @property
    def expires(self) -> datetime.datetime:
        """
        The `datetime` at which the QR code will expire.

        If you want to try again, you will need to call `recreate`.
        """
        return self._resp.expires

    async def wait(self, timeout: float = None):
        """
        Waits for the token to be imported by a previously-authorized client,
        either by scanning the QR, launching the URL directly, or calling the
        import method.

        This method **must** be called before the QR code is scanned, and
        must be executing while the QR code is being scanned. Otherwise, the
        login will not complete.

        Will raise `asyncio.TimeoutError` if the login doesn't complete on
        time.

        Arguments
            timeout (float):
                The timeout, in seconds, to wait before giving up. By default
                the library will wait until the token expires, which is often
                what you want.

        Returns
            On success, an instance of :tl:`User`. On failure it will raise.
        """
        if timeout is None:
            timeout = (self._resp.expires - datetime.datetime.now(tz=datetime.timezone.utc)).total_seconds()

        event = asyncio.Event()

        async def handler(_update):
            event.set()

        self._client.add_event_handler(handler, events.Raw(types.UpdateLoginToken))

        try:
            # Will raise timeout error if it doesn't complete quick enough,
            # which we want to let propagate
            await asyncio.wait_for(event.wait(), timeout=timeout)
        finally:
            self._client.remove_event_handler(handler)

        # We got here without it raising timeout error, so we can proceed
        resp = await self._client(self._request)
        if isinstance(resp, types.auth.LoginTokenMigrateTo):
            await self._client._switch_dc(resp.dc_id)
            resp = await self._client(functions.auth.ImportLoginTokenRequest(resp.token))
            # resp should now be auth.loginTokenSuccess

        if isinstance(resp, types.auth.LoginTokenSuccess):
            user = resp.authorization.user
            self._client._on_login(user)
            return user

        raise TypeError('Login token response was unexpected: {}'.format(resp))
