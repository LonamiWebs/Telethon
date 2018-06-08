import logging
import platform
from datetime import timedelta, datetime

from . import version, utils
from .crypto import rsa
from .extensions import markdown
from .network import MTProtoSender, ConnectionTcpFull
from .sessions import Session, SQLiteSession
from .tl import TLObject
from .tl.all_tlobjects import LAYER
from .tl.functions import (
    InitConnectionRequest, InvokeWithLayerRequest
)
from .tl.functions.auth import (
    ImportAuthorizationRequest, ExportAuthorizationRequest
)
from .tl.functions.help import (
    GetCdnConfigRequest, GetConfigRequest
)
from .tl.types.auth import ExportedAuthorization
from .update_state import UpdateState

DEFAULT_DC_ID = 4
DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '[2001:67c:4e8:f002::a]'
DEFAULT_PORT = 443

__log__ = logging.getLogger(__name__)


# TODO Do we need this class?
class TelegramBareClient:
    """
    A bare Telegram client that somewhat eases the usage of the
    ``MTProtoSender``.

    Args:
        session (`str` | `telethon.sessions.abstract.Session`, `None`):
            The file name of the session file to be used if a string is
            given (it may be a full path), or the Session instance to be
            used otherwise. If it's ``None``, the session will not be saved,
            and you should call :meth:`.log_out()` when you're done.

            Note that if you pass a string it will be a file in the current
            working directory, although you can also pass absolute paths.

            The session file contains enough information for you to login
            without re-sending the code, so if you have to enter the code
            more than once, maybe you're changing the working directory,
            renaming or removing the file, or using random names.

        api_id (`int` | `str`):
            The API ID you obtained from https://my.telegram.org.

        api_hash (`str`):
            The API ID you obtained from https://my.telegram.org.

        connection (`telethon.network.connection.common.Connection`, optional):
            The connection instance to be used when creating a new connection
            to the servers. If it's a type, the `proxy` argument will be used.

            Defaults to `telethon.network.connection.tcpfull.ConnectionTcpFull`.

        use_ipv6 (`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is ``False`` as IPv6 support is not
            too widespread yet.

        proxy (`tuple` | `dict`, optional):
            A tuple consisting of ``(socks.SOCKS5, 'host', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        update_workers (`int`, optional):
            If specified, represents how many extra threads should
            be spawned to handle incoming updates, and updates will
            be kept in memory until they are processed. Note that
            you must set this to at least ``0`` if you want to be
            able to process updates through :meth:`updates.poll()`.

        timeout (`int` | `float` | `timedelta`, optional):
            The timeout to be used when receiving responses from
            the network. Defaults to 5 seconds.

        spawn_read_thread (`bool`, optional):
            Whether to use an extra background thread or not. Defaults
            to ``True`` so receiving items from the network happens
            instantly, as soon as they arrive. Can still be disabled
            if you want to run the library without any additional thread.

        report_errors (`bool`, optional):
            Whether to report RPC errors or not. Defaults to ``True``,
            see :ref:`api-status` for more information.

        device_model (`str`, optional):
            "Device model" to be sent when creating the initial connection.
            Defaults to ``platform.node()``.

        system_version (`str`, optional):
            "System version" to be sent when creating the initial connection.
            Defaults to ``platform.system()``.

        app_version (`str`, optional):
            "App version" to be sent when creating the initial connection.
            Defaults to `telethon.version.__version__`.

        lang_code (`str`, optional):
            "Language code" to be sent when creating the initial connection.
            Defaults to ``'en'``.

        system_lang_code (`str`, optional):
            "System lang code"  to be sent when creating the initial connection.
            Defaults to `lang_code`.
    """

    # Current TelegramClient version
    __version__ = version.__version__

    # Server configuration (with .dc_options)
    _config = None

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 *,
                 connection=ConnectionTcpFull,
                 use_ipv6=False,
                 proxy=None,
                 timeout=timedelta(seconds=5),
                 report_errors=True,
                 device_model=None,
                 system_version=None,
                 app_version=None,
                 lang_code='en',
                 system_lang_code='en'):
        """Refer to TelegramClient.__init__ for docs on this method"""
        if not api_id or not api_hash:
            raise ValueError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to telethon.rtfd.io for more information.")

        self._use_ipv6 = use_ipv6

        # Determine what session object we have
        if isinstance(session, str) or session is None:
            session = SQLiteSession(session)
        elif not isinstance(session, Session):
            raise TypeError(
                'The given session must be a str or a Session instance.'
            )

        # ':' in session.server_address is True if it's an IPv6 address
        if (not session.server_address or
                (':' in session.server_address) != use_ipv6):
            session.set_dc(
                DEFAULT_DC_ID,
                DEFAULT_IPV6_IP if self._use_ipv6 else DEFAULT_IPV4_IP,
                DEFAULT_PORT
            )

        session.report_errors = report_errors
        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash

        # This is the main sender, which will be used from the thread
        # that calls .connect(). Every other thread will spawn a new
        # temporary connection. The connection on this one is always
        # kept open so Telegram can send us updates.
        if isinstance(connection, type):
            connection = connection(proxy=proxy, timeout=timeout)

        self._sender = MTProtoSender(self.session, connection)

        # Cache "exported" sessions as 'dc_id: Session' not to recreate
        # them all the time since generating a new key is a relatively
        # expensive operation.
        self._exported_sessions = {}

        # This member will process updates if enabled.
        # One may change self.updates.enabled at any later point.
        # TODO Stop using that 1
        self.updates = UpdateState(1)

        # Used on connection - the user may modify these and reconnect
        system = platform.uname()
        self.device_model = device_model or system.system or 'Unknown'
        self.system_version = system_version or system.release or '1.0'
        self.app_version = app_version or self.__version__
        self.lang_code = lang_code
        self.system_lang_code = system_lang_code

        # Save whether the user is authorized here (a.k.a. logged in)
        self._authorized = None  # None = We don't know yet

        # The first request must be in invokeWithLayer(initConnection(X)).
        # See https://core.telegram.org/api/invoking#saving-client-info.
        self._first_request = True

        # Default PingRequest delay
        self._last_ping = datetime.now()
        self._ping_delay = timedelta(minutes=1)

        # Also have another delay for GetStateRequest.
        #
        # If the connection is kept alive for long without invoking any
        # high level request the server simply stops sending updates.
        # TODO maybe we can have ._last_request instead if any req works?
        self._last_state = datetime.now()
        self._state_delay = timedelta(hours=1)

        # Some further state for subclasses
        self._event_builders = []
        self._events_pending_resolve = []

        # Default parse mode
        self._parse_mode = markdown

        # Some fields to easy signing in. Let {phone: hash} be
        # a dictionary because the user may change their mind.
        self._phone_code_hash = {}
        self._phone = None
        self._tos = None

        # Sometimes we need to know who we are, cache the self peer
        self._self_input_peer = None

    # endregion

    # region Connecting

    async def connect(self, _sync_updates=True):
        """
        Connects to Telegram.
        """
        # TODO Maybe we should rethink what the session does if the sender
        # needs a session but it might connect to arbitrary IPs?
        #
        # TODO sync updates/connected and authorized if no UnauthorizedError?
        await self._sender.connect(
            self.session.server_address, self.session.port)

    def is_connected(self):
        """
        Returns ``True`` if the user has connected.
        """
        return self._sender.is_connected()

    def _wrap_init_connection(self, query):
        """
        Wraps `query` around
        ``InvokeWithLayerRequest(InitConnectionRequest(...))``.
        """
        return InvokeWithLayerRequest(LAYER, InitConnectionRequest(
            api_id=self.api_id,
            device_model=self.device_model,
            system_version=self.system_version,
            app_version=self.app_version,
            lang_code=self.lang_code,
            system_lang_code=self.system_lang_code,
            lang_pack='',  # "langPacks are for official apps only"
            query=query
        ))

    async def disconnect(self):
        """
        Disconnects from Telegram.
        """
        await self._sender.disconnect()
        # TODO What to do with the update state? Does it belong here?
        # self.session.set_update_state(0, self.updates.get_update_state(0))
        self.session.close()

    def _switch_dc(self, new_dc):
        """
        Switches the current connection to the new data center.
        """
        # TODO Implement
        raise NotImplementedError
        dc = self._get_dc(new_dc)
        __log__.info('Reconnecting to new data center %s', dc)

        self.session.set_dc(dc.id, dc.ip_address, dc.port)
        # auth_key's are associated with a server, which has now changed
        # so it's not valid anymore. Set to None to force recreating it.
        self.session.auth_key = None
        self.session.save()
        self.disconnect()
        return self.connect()

    def set_proxy(self, proxy):
        """Change the proxy used by the connections.
        """
        if self.is_connected():
            raise RuntimeError("You can't change the proxy while connected.")

        # TODO Should we tell the user to create a new client?
        # Can this be done more cleanly? Similar to `switch_dc`
        self._sender._connection.conn.proxy = proxy

    # endregion

    # region Working with different connections/Data Centers

    def _get_dc(self, dc_id, cdn=False):
        """Gets the Data Center (DC) associated to 'dc_id'"""
        if not TelegramBareClient._config:
            TelegramBareClient._config = self(GetConfigRequest())

        try:
            if cdn:
                # Ensure we have the latest keys for the CDNs
                for pk in self(GetCdnConfigRequest()).public_keys:
                    rsa.add_key(pk.public_key)

            return next(
                dc for dc in TelegramBareClient._config.dc_options
                if dc.id == dc_id and bool(dc.ipv6) == self._use_ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            if not cdn:
                raise

            # New configuration, perhaps a new CDN was added?
            TelegramBareClient._config = self(GetConfigRequest())
            return self._get_dc(dc_id, cdn=cdn)

    def _get_exported_client(self, dc_id):
        """Creates and connects a new TelegramBareClient for the desired DC.

           If it's the first time calling the method with a given dc_id,
           a new session will be first created, and its auth key generated.
           Exporting/Importing the authorization will also be done so that
           the auth is bound with the key.
        """
        # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
        # for clearly showing how to export the authorization! ^^
        session = self._exported_sessions.get(dc_id)
        if session:
            export_auth = None  # Already bound with the auth key
        else:
            # TODO Add a lock, don't allow two threads to create an auth key
            # (when calling .connect() if there wasn't a previous session).
            # for the same data center.
            dc = self._get_dc(dc_id)

            # Export the current authorization to the new DC.
            __log__.info('Exporting authorization for data center %s', dc)
            export_auth = self(ExportAuthorizationRequest(dc_id))

            # Create a temporary session for this IP address, which needs
            # to be different because each auth_key is unique per DC.
            #
            # Construct this session with the connection parameters
            # (system version, device model...) from the current one.
            session = self.session.clone()
            session.set_dc(dc.id, dc.ip_address, dc.port)
            self._exported_sessions[dc_id] = session

        __log__.info('Creating exported new client')
        client = TelegramBareClient(
            session, self.api_id, self.api_hash,
            proxy=self._sender.connection.conn.proxy,
            timeout=self._sender.connection.get_timeout()
        )
        client.connect(_sync_updates=False)
        if isinstance(export_auth, ExportedAuthorization):
            client(ImportAuthorizationRequest(
                id=export_auth.id, bytes=export_auth.bytes
            ))
        elif export_auth is not None:
            __log__.warning('Unknown export auth type %s', export_auth)

        client._authorized = True  # We exported the auth, so we got auth
        return client

    def _get_cdn_client(self, cdn_redirect):
        """Similar to ._get_exported_client, but for CDNs"""
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = self.session.clone()
            session.set_dc(dc.id, dc.ip_address, dc.port)
            self._exported_sessions[cdn_redirect.dc_id] = session

        __log__.info('Creating new CDN client')
        client = TelegramBareClient(
            session, self.api_id, self.api_hash,
            proxy=self._sender.connection.conn.proxy,
            timeout=self._sender.connection.get_timeout()
        )

        # This will make use of the new RSA keys for this specific CDN.
        #
        # We won't be calling GetConfigRequest because it's only called
        # when needed by ._get_dc, and also it's static so it's likely
        # set already. Avoid invoking non-CDN methods by not syncing updates.
        client.connect(_sync_updates=False)
        client._authorized = self._authorized
        return client

    # endregion

    # region Invoking Telegram requests

    async def __call__(self, request, ordered=False):
        """
        Invokes (sends) one or more MTProtoRequests and returns (receives)
        their result.

        Args:
            request (`TLObject` | `list`):
                The request or requests to be invoked.

            retries (`bool`, optional):
                How many times the request should be retried automatically
                in case it fails with a non-RPC error.

               The invoke will be retried up to 'retries' times before raising
               ``RuntimeError``.

            ordered (`bool`, optional):
                Whether the requests (if more than one was given) should be
                executed sequentially on the server. They run in arbitrary
                order by default.

        Returns:
            The result of the request (often a `TLObject`) or a list of
            results if more than one request was given.
        """
        requests = (request,) if not utils.is_list_like(request) else request
        if not all(isinstance(x, TLObject) and
                   x.content_related for x in requests):
            raise TypeError('You can only invoke requests, not types!')

        # TODO Resolve requests, should be done by TelegramClient
        # for r in requests:
        #    await r.resolve(self, utils)

        # TODO InvokeWithLayer if no authkey, maybe done in MTProtoSender?
        # TODO Handle PhoneMigrateError, NetworkMigrateError, UserMigrateError
        #      ^ by switching DC
        # TODO Retry on ServerError, RpcCallFailError
        # TODO Auto-sleep on some FloodWaitError, FloodTestPhoneWaitError
        future = await self._sender.send(request, ordered=ordered)
        if isinstance(future, list):
            results = []
            for f in future:
                results.append(await future)
            return results
        else:
            return await future

    # Let people use client.invoke(SomeRequest()) instead client(...)
    invoke = __call__

    # endregion
