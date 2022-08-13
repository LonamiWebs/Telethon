import asyncio
import base64
import time
import functools

from ... import _tl
from ..._events.raw import Raw


class QrLoginManager:
    def __init__(self, client, ignored_ids):
        self._client = client
        self._request = _tl.fn.auth.ExportLoginToken(client._api_id, client._api_hash, ignored_ids or [])
        self._event = None
        self._handler = None
        self._login = None

    async def __aenter__(self):
        self._event = asyncio.Event()
        self._handler = self._client.add_event_handler(self._callback, Raw)

        try:
            qr = await self._client(self._request)
        except:
            self._cleanup()
            raise

        self._login = QrLogin._new(self._client, self._request, qr, self._event)
        return self._login

    async def __aexit__(self, *args):
        try:
            # The logic to complete the login is in wait so the user can retrieve the logged-in user
            await self._login.wait(timeout=0)
            # User logged-in in time
        except asyncio.TimeoutError:
            pass  # User did not login in time
        finally:
            self._cleanup()

    async def _callback(self, update):
        if isinstance(update, _tl.UpdateLoginToken):
            self._event.set()

    def _cleanup(self):
        # Users technically could remove all raw handlers during the procedure but it's unlikely to happen
        self._client.remove_event_handler(self._handler)
        self._event = None
        self._handler = None
        self._login = None


class QrLogin:
    """
    QR login information.

    Most of the time, you will present the `url` as a QR code to the user,
    and while it's being shown, call `wait`.
    """
    def __init__(self):
        raise TypeError('You cannot create QrLogin instances by hand!')

    @classmethod
    def _new(cls, client, request, qr, event):
        self = cls.__new__(cls)
        self._client = client
        self._request = request
        self._qr = qr
        self._expiry = asyncio.get_running_loop().time() + qr.expires.timestamp() - time.time()
        self._event = event
        self._user = None
        return self

    @property
    def token(self) -> bytes:
        """
        The binary data representing the token.

        It can be used by a previously-authorized client in a call to
        :tl:`auth.importLoginToken` to log the client that originally
        requested the QR login.
        """
        return self._qr.token

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
        return 'tg://login?token={}'.format(base64.urlsafe_b64encode(self._qr.token).decode('utf-8').rstrip('='))

    @property
    def timeout(self):
        """
        How many seconds are left before `client.qr_login` should be used again.

        This value is a positive floating point number, and is monotically decreasing.
        The value will reach zero after enough seconds have elapsed. This lets you do some work
        and call sleep on the value and still wait just long enough.
        """
        return max(0.0, self._expiry - asyncio.get_running_loop().time())

    @property
    def expired(self):
        """
        Returns `True` if this instance of the QR login has expired and should be re-created.

        .. code-block:: python

            if qr.expired:
                qr = await client.qr_login()
        """
        return asyncio.get_running_loop().time() >= self._expiry

    async def wait(self, timeout: float = None):
        """
        Waits for the token to be imported by a previously-authorized client,
        either by scanning the QR, launching the URL directly, or calling the
        import method.

        Will raise `asyncio.TimeoutError` if the login doesn't complete on
        time.

        Note that the login can complete even if `wait` isn't used (if the
        context-manager is kept alive for long enough and the users logs in).

        Arguments
            timeout (float):
                The timeout, in seconds, to wait before giving up. By default
                the library will wait until the token expires, which is often
                what you want.

        Returns
            On success, an instance of `User`. On failure it will raise.
        """
        if self._user:
            return self._user

        if timeout is None:
            timeout = self.timeout

        # Will raise timeout error if it doesn't complete quick enough,
        # which we want to let propagate
        await asyncio.wait_for(self._event.wait(), timeout=timeout)

        resp = await self._client(self._request)
        if isinstance(resp, _tl.auth.LoginTokenMigrateTo):
            await self._client._switch_dc(resp.dc_id)
            resp = await self._client(_tl.fn.auth.ImportLoginToken(resp.token))
            # resp should now be auth.loginTokenSuccess

        if isinstance(resp, _tl.auth.LoginTokenSuccess):
            user = resp.authorization.user
            self._user = self._client._update_session_state(user)
            return self._user

        raise RuntimeError(f'Unexpected login token response: {resp}')
