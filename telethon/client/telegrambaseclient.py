import abc
import asyncio
import collections
import inspect
import logging
import platform
import sys
import time
from datetime import timedelta, datetime

from .. import version
from ..crypto import rsa
from ..extensions import markdown
from ..network import MTProtoSender, ConnectionTcpFull
from ..network.mtprotostate import MTProtoState
from ..sessions import Session, SQLiteSession, MemorySession
from ..tl import TLObject, functions, types
from ..tl.alltlobjects import LAYER

DEFAULT_DC_ID = 4
DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '[2001:67c:4e8:f002::a]'
DEFAULT_PORT = 443

__log__ = logging.getLogger(__name__)


class TelegramBaseClient(abc.ABC):
    """
    This is the abstract base class for the client. It defines some
    basic stuff like connecting, switching data center, etc, and
    leaves the `__call__` unimplemented.

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

        timeout (`int` | `float` | `timedelta`, optional):
            The timeout to be used when connecting, sending and receiving
            responses from the network. This is **not** the timeout to
            be used when ``await``'ing for invoked requests, and you
            should use ``asyncio.wait`` or ``asyncio.wait_for`` for that.

        request_retries (`int`, optional):
            How many times a request should be retried. Request are retried
            when Telegram is having internal issues (due to either
            ``errors.ServerError`` or ``errors.RpcCallFailError``),
            when there is a ``errors.FloodWaitError`` less than
            `flood_sleep_threshold`, or when there's a migrate error.

            May set to a false-y value (``0`` or ``None``) for infinite
            retries, but this is not recommended, since some requests can
            always trigger a call fail (such as searching for messages).

        connection_retries (`int`, optional):
            How many times the reconnection should retry, either on the
            initial connection or when Telegram disconnects us. May be
            set to a false-y value (``0`` or ``None``) for infinite
            retries, but this is not recommended, since the program can
            get stuck in an infinite loop.

        auto_reconnect (`bool`, optional):
            Whether reconnection should be retried `connection_retries`
            times automatically if Telegram disconnects us or not.

        sequential_updates (`bool`, optional):
            By default every incoming update will create a new task, so
            you can handle several updates in parallel. Some scripts need
            the order in which updates are processed to be sequential, and
            this setting allows them to do so.

            If set to ``True``, incoming updates will be put in a queue
            and processed sequentially. This means your event handlers
            should *not* perform long-running operations since new
            updates are put inside of an unbounded queue.

        flood_sleep_threshold (`int` | `float`, optional):
            The threshold below which the library should automatically
            sleep on flood wait errors (inclusive). For instance, if a
            ``FloodWaitError`` for 17s occurs and `flood_sleep_threshold`
            is 20s, the library will ``sleep`` automatically. If the error
            was for 21s, it would ``raise FloodWaitError`` instead. Values
            larger than a day (like ``float('inf')``) will be changed to a day.

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

    # Cached server configuration (with .dc_options), can be "global"
    _config = None
    _cdn_config = None

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 *,
                 connection=ConnectionTcpFull,
                 use_ipv6=False,
                 proxy=None,
                 timeout=timedelta(seconds=10),
                 request_retries=5,
                 connection_retries=5,
                 auto_reconnect=True,
                 sequential_updates=False,
                 flood_sleep_threshold=60,
                 device_model=None,
                 system_version=None,
                 app_version=None,
                 lang_code='en',
                 system_lang_code='en',
                 loop=None):
        if not api_id or not api_hash:
            raise ValueError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to telethon.rtfd.io for more information.")

        self._use_ipv6 = use_ipv6
        self._loop = loop or asyncio.get_event_loop()

        # Determine what session object we have
        if isinstance(session, str) or session is None:
            try:
                session = SQLiteSession(session)
            except ValueError:
                import warnings
                warnings.warn(
                    'The sqlite3 module is not available under this '
                    'Python installation and no custom session '
                    'instance was given; using MemorySession.\n'
                    'You will need to re-login every time unless '
                    'you use another session storage'
                )
                session = MemorySession()
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

        self.flood_sleep_threshold = flood_sleep_threshold
        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash

        self._request_retries = request_retries or sys.maxsize
        self._connection_retries = connection_retries or sys.maxsize
        self._auto_reconnect = auto_reconnect

        if isinstance(connection, type):
            connection = connection(
                proxy=proxy, timeout=timeout, loop=self._loop)

        # Used on connection. Capture the variables in a lambda since
        # exporting clients need to create this InvokeWithLayerRequest.
        system = platform.uname()
        self._init_with = lambda x: functions.InvokeWithLayerRequest(
            LAYER, functions.InitConnectionRequest(
                api_id=self.api_id,
                device_model=device_model or system.system or 'Unknown',
                system_version=system_version or system.release or '1.0',
                app_version=app_version or self.__version__,
                lang_code=lang_code,
                system_lang_code=system_lang_code,
                lang_pack='',  # "langPacks are for official apps only"
                query=x
            )
        )

        state = MTProtoState(self.session.auth_key)
        self._connection = connection
        self._sender = MTProtoSender(
            state, connection, self._loop,
            retries=self._connection_retries,
            auto_reconnect=self._auto_reconnect,
            update_callback=self._handle_update,
            auth_key_callback=self._auth_key_callback,
            auto_reconnect_callback=self._handle_auto_reconnect
        )

        # Remember flood-waited requests to avoid making them again
        self._flood_waited_requests = {}

        # Cache ``{dc_id: (n, MTProtoSender)}`` for all borrowed senders,
        # being ``n`` the amount of borrows a given sender has; once ``n``
        # reaches ``0`` it should be disconnected and removed.
        self._borrowed_senders = {}
        self._borrow_sender_lock = asyncio.Lock(loop=self._loop)

        # Save whether the user is authorized here (a.k.a. logged in)
        self._authorized = None  # None = We don't know yet

        # Default PingRequest delay
        self._last_ping = datetime.now()
        self._ping_delay = timedelta(minutes=1)

        self._updates_handle = None
        self._last_request = time.time()
        self._channel_pts = {}

        if sequential_updates:
            self._updates_queue = asyncio.Queue(loop=self._loop)
            self._dispatching_updates_queue = asyncio.Event(loop=self._loop)
        else:
            self._updates_queue = None
            self._dispatching_updates_queue = None

        # Start with invalid state (-1) so we can have somewhere to store
        # the state, but also be able to determine if we are authorized.
        self._state = types.updates.State(-1, 0, datetime.now(), 0, -1)

        # Some further state for subclasses
        self._event_builders = []
        self._conversations = {}

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

    # region Properties

    @property
    def loop(self):
        return self._loop

    @property
    def disconnected(self):
        """
        Future that resolves when the connection to Telegram
        ends, either by user action or in the background.
        """
        return self._sender.disconnected

    # endregion

    # region Connecting

    async def connect(self):
        """
        Connects to Telegram.
        """
        await self._sender.connect(
            self.session.server_address, self.session.port)

        await self._sender.send(self._init_with(
            functions.help.GetConfigRequest()))

        self._updates_handle = self._loop.create_task(self._update_loop())

    def is_connected(self):
        """
        Returns ``True`` if the user has connected.
        """
        sender = getattr(self, '_sender', None)
        return sender and sender.is_connected()

    async def disconnect(self):
        """
        Disconnects from Telegram.
        """
        await self._disconnect()
        if getattr(self, 'session', None):
            if getattr(self, '_state', None):
                self.session.set_update_state(0, self._state)
            self.session.close()

    async def _disconnect(self):
        """
        Disconnect only, without closing the session. Used in reconnections
        to different data centers, where we don't want to close the session
        file; user disconnects however should close it since it means that
        their job with the client is complete and we should clean it up all.
        """
        # All properties may be ``None`` if `__init__` fails, and this
        # method will be called from `__del__` which would crash then.
        if getattr(self, '_sender', None):
            await self._sender.disconnect()
        if getattr(self, '_updates_handle', None):
            await self._updates_handle

    def __del__(self):
        if not self.is_connected() or self.loop.is_closed():
            return

        # Python 3.5.2's ``asyncio`` mod seems to have a bug where it's not
        # able to close the pending tasks properly, and letting the script
        # complete without calling disconnect causes the script to trigger
        # 100% CPU load. Call disconnect to make sure it doesn't happen.
        if not inspect.iscoroutinefunction(self.disconnect):
            self.disconnect()
        elif self._loop.is_running():
            self._loop.create_task(self.disconnect())
        else:
            self._loop.run_until_complete(self.disconnect())

    async def _switch_dc(self, new_dc):
        """
        Permanently switches the current connection to the new data center.
        """
        __log__.info('Reconnecting to new data center %s', new_dc)
        dc = await self._get_dc(new_dc)

        self.session.set_dc(dc.id, dc.ip_address, dc.port)
        # auth_key's are associated with a server, which has now changed
        # so it's not valid anymore. Set to None to force recreating it.
        self.session.auth_key = self._sender.state.auth_key = None
        self.session.save()
        await self._disconnect()
        return await self.connect()

    def _auth_key_callback(self, auth_key):
        """
        Callback from the sender whenever it needed to generate a
        new authorization key. This means we are not authorized.
        """
        self._authorized = None
        self.session.auth_key = auth_key
        self.session.save()

    # endregion

    # region Working with different connections/Data Centers

    async def _get_dc(self, dc_id, cdn=False):
        """Gets the Data Center (DC) associated to 'dc_id'"""
        cls = self.__class__
        if not cls._config:
            cls._config = await self(functions.help.GetConfigRequest())

        if cdn and not self._cdn_config:
            cls._cdn_config = await self(functions.help.GetCdnConfigRequest())
            for pk in cls._cdn_config.public_keys:
                rsa.add_key(pk.public_key)

        return next(
            dc for dc in cls._config.dc_options
            if dc.id == dc_id
            and bool(dc.ipv6) == self._use_ipv6 and bool(dc.cdn) == cdn
        )

    async def _create_exported_sender(self, dc_id):
        """
        Creates a new exported `MTProtoSender` for the given `dc_id` and
        returns it. This method should be used by `_borrow_exported_sender`.
        """
        # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
        # for clearly showing how to export the authorization
        dc = await self._get_dc(dc_id)
        state = MTProtoState(None)
        # Can't reuse self._sender._connection as it has its own seqno.
        #
        # If one were to do that, Telegram would reset the connection
        # with no further clues.
        sender = MTProtoSender(state, self._connection.clone(), self._loop)
        await sender.connect(dc.ip_address, dc.port)
        __log__.info('Exporting authorization for data center %s', dc)
        auth = await self(functions.auth.ExportAuthorizationRequest(dc_id))
        req = self._init_with(functions.auth.ImportAuthorizationRequest(
            id=auth.id, bytes=auth.bytes
        ))
        await sender.send(req)
        return sender

    async def _borrow_exported_sender(self, dc_id):
        """
        Borrows a connected `MTProtoSender` for the given `dc_id`.
        If it's not cached, creates a new one if it doesn't exist yet,
        and imports a freshly exported authorization key for it to be usable.

        Once its job is over it should be `_return_exported_sender`.
        """
        async with self._borrow_sender_lock:
            n, sender = self._borrowed_senders.get(dc_id, (0, None))
            if not sender:
                sender = await self._create_exported_sender(dc_id)
                sender.dc_id = dc_id
            elif not n:
                dc = await self._get_dc(dc_id)
                await sender.connect(dc.ip_address, dc.port)

            self._borrowed_senders[dc_id] = (n + 1, sender)

        return sender

    async def _return_exported_sender(self, sender):
        """
        Returns a borrowed exported sender. If all borrows have
        been returned, the sender is cleanly disconnected.
        """
        async with self._borrow_sender_lock:
            dc_id = sender.dc_id
            n, _ = self._borrowed_senders[dc_id]
            n -= 1
            self._borrowed_senders[dc_id] = (n, sender)
            if not n:
                __log__.info('Disconnecting borrowed sender for DC %d', dc_id)
                await sender.disconnect()

    async def _get_cdn_client(self, cdn_redirect):
        """Similar to ._borrow_exported_client, but for CDNs"""
        # TODO Implement
        raise NotImplementedError
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
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

    @abc.abstractmethod
    def __call__(self, request, ordered=False):
        """
        Invokes (sends) one or more MTProtoRequests and returns (receives)
        their result.

        Args:
            request (`TLObject` | `list`):
                The request or requests to be invoked.

            ordered (`bool`, optional):
                Whether the requests (if more than one was given) should be
                executed sequentially on the server. They run in arbitrary
                order by default.

        Returns:
            The result of the request (often a `TLObject`) or a list of
            results if more than one request was given.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _handle_update(self, update):
        raise NotImplementedError

    @abc.abstractmethod
    def _update_loop(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def _handle_auto_reconnect(self):
        raise NotImplementedError

    # endregion
