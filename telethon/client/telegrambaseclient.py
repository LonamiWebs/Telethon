import abc
import asyncio
import logging
import platform
import time
import typing

from .. import version, helpers, __name__ as __base_name__
from ..crypto import rsa
from ..entitycache import EntityCache
from ..extensions import markdown
from ..network import MTProtoSender, Connection, ConnectionTcpFull, TcpMTProxy
from ..sessions import Session, SQLiteSession, MemorySession
from ..statecache import StateCache
from ..tl import TLObject, functions, types
from ..tl.alltlobjects import LAYER

DEFAULT_DC_ID = 4
DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '[2001:67c:4e8:f002::a]'
DEFAULT_PORT = 443

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

__default_log__ = logging.getLogger(__base_name__)
__default_log__.addHandler(logging.NullHandler())


# TODO How hard would it be to support both `trio` and `asyncio`?
class TelegramBaseClient(abc.ABC):
    """
    This is the abstract base class for the client. It defines some
    basic stuff like connecting, switching data center, etc, and
    leaves the `__call__` unimplemented.

    Arguments
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
            to the servers. It **must** be a type.

            Defaults to `telethon.network.connection.tcpfull.ConnectionTcpFull`.

        use_ipv6 (`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is ``False`` as IPv6 support is not
            too widespread yet.

        proxy (`tuple` | `list` | `dict`, optional):
            An iterable consisting of the proxy info. If `connection` is
            one of `MTProxy`, then it should contain MTProxy credentials:
            ``('hostname', port, 'secret')``. Otherwise, it's meant to store
            function parameters for PySocks, like ``(type, 'hostname', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        timeout (`int` | `float`, optional):
            The timeout in seconds to be used when connecting.
            This is **not** the timeout to be used when ``await``'ing for
            invoked requests, and you should use ``asyncio.wait`` or
            ``asyncio.wait_for`` for that.

        request_retries (`int` | `None`, optional):
            How many times a request should be retried. Request are retried
            when Telegram is having internal issues (due to either
            ``errors.ServerError`` or ``errors.RpcCallFailError``),
            when there is a ``errors.FloodWaitError`` less than
            `flood_sleep_threshold`, or when there's a migrate error.

            May take a negative or ``None`` value for infinite retries, but
            this is not recommended, since some requests can always trigger
            a call fail (such as searching for messages).

        connection_retries (`int` | `None`, optional):
            How many times the reconnection should retry, either on the
            initial connection or when Telegram disconnects us. May be
            set to a negative or ``None`` value for infinite retries, but
            this is not recommended, since the program can get stuck in an
            infinite loop.

        retry_delay (`int` | `float`, optional):
            The delay in seconds to sleep between automatic reconnections.

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

        loop (`asyncio.AbstractEventLoop`, optional):
            Asyncio event loop to use. Defaults to `asyncio.get_event_loop()`

        base_logger (`str` | `logging.Logger`, optional):
            Base logger name or instance to use.
            If a `str` is given, it'll be passed to `logging.getLogger()`. If a
            `logging.Logger` is given, it'll be used directly. If something
            else or nothing is given, the default logger will be used.
    """

    # Current TelegramClient version
    __version__ = version.__version__

    # Cached server configuration (with .dc_options), can be "global"
    _config = None
    _cdn_config = None

    # region Initialization

    def __init__(
            self: 'TelegramClient',
            session: 'typing.Union[str, Session]',
            api_id: int,
            api_hash: str,
            *,
            connection: 'typing.Type[Connection]' = ConnectionTcpFull,
            use_ipv6: bool = False,
            proxy: typing.Union[tuple, dict] = None,
            timeout: int = 10,
            request_retries: int = 5,
            connection_retries: int =5,
            retry_delay: int = 1,
            auto_reconnect: bool = True,
            sequential_updates: bool = False,
            flood_sleep_threshold: int = 60,
            device_model: str = None,
            system_version: str = None,
            app_version: str = None,
            lang_code: str = 'en',
            system_lang_code: str = 'en',
            loop: asyncio.AbstractEventLoop = None,
            base_logger: typing.Union[str, logging.Logger] = None):
        if not api_id or not api_hash:
            raise ValueError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to telethon.rtfd.io for more information.")

        self._use_ipv6 = use_ipv6
        self._loop = loop or asyncio.get_event_loop()

        if isinstance(base_logger, str):
            base_logger = logging.getLogger(base_logger)
        elif not isinstance(base_logger, logging.Logger):
            base_logger = __default_log__

        class _Loggers(dict):
            def __missing__(self, key):
                if key.startswith("telethon."):
                    key = key.split('.', maxsplit=1)[1]

                return base_logger.getChild(key)

        self._log = _Loggers()

        # Determine what session object we have
        if isinstance(session, str) or session is None:
            try:
                session = SQLiteSession(session)
            except ImportError:
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

        # TODO Use AsyncClassWrapper(session)
        # ChatGetter and SenderGetter can use the in-memory _entity_cache
        # to avoid network access and the need for await in session files.
        #
        # The session files only wants the entities to persist
        # them to disk, and to save additional useful information.
        # TODO Session should probably return all cached
        #      info of entities, not just the input versions
        self.session = session
        self._entity_cache = EntityCache()
        self.api_id = int(api_id)
        self.api_hash = api_hash

        self._request_retries = request_retries
        self._connection_retries = connection_retries
        self._retry_delay = retry_delay or 0
        self._proxy = proxy
        self._timeout = timeout
        self._auto_reconnect = auto_reconnect

        assert isinstance(connection, type)
        self._connection = connection
        init_proxy = None if not issubclass(connection, TcpMTProxy) else \
            types.InputClientProxy(*connection.address_info(proxy))

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
                query=x,
                proxy=init_proxy
            )
        )

        self._sender = MTProtoSender(
            self.session.auth_key, self._loop,
            loggers=self._log,
            retries=self._connection_retries,
            delay=self._retry_delay,
            auto_reconnect=self._auto_reconnect,
            connect_timeout=self._timeout,
            auth_key_callback=self._auth_key_callback,
            update_callback=self._handle_update,
            auto_reconnect_callback=self._handle_auto_reconnect
        )

        # Remember flood-waited requests to avoid making them again
        self._flood_waited_requests = {}

        # Cache ``{dc_id: (n, MTProtoSender)}`` for all borrowed senders,
        # being ``n`` the amount of borrows a given sender has; once ``n``
        # reaches ``0`` it should be disconnected and removed.
        self._borrowed_senders = {}
        self._borrow_sender_lock = asyncio.Lock(loop=self._loop)

        self._updates_handle = None
        self._last_request = time.time()
        self._channel_pts = {}

        if sequential_updates:
            self._updates_queue = asyncio.Queue(loop=self._loop)
            self._dispatching_updates_queue = asyncio.Event(loop=self._loop)
        else:
            # Use a set of pending instead of a queue so we can properly
            # terminate all pending updates on disconnect.
            self._updates_queue = set()
            self._dispatching_updates_queue = None

        self._authorized = None  # None = unknown, False = no, True = yes

        # Update state (for catching up after a disconnection)
        # TODO Get state from channels too
        self._state_cache = StateCache(
            self.session.get_update_state(0), self._log)

        # Some further state for subclasses
        self._event_builders = []
        self._conversations = {}
        self._ids_in_conversations = {}  # chat_id: count

        # Default parse mode
        self._parse_mode = markdown

        # Some fields to easy signing in. Let {phone: hash} be
        # a dictionary because the user may change their mind.
        self._phone_code_hash = {}
        self._phone = None
        self._tos = None

        # Sometimes we need to know who we are, cache the self peer
        self._self_input_peer = None
        self._bot = None

    # endregion

    # region Properties

    @property
    def loop(self: 'TelegramClient') -> asyncio.AbstractEventLoop:
        """
        Property with the ``asyncio`` event loop used by this client.

        Example
            .. code-block:: python

                # Download media in the background
                task = client.loop_create_task(message.download_media())

                # Do some work
                ...

                # Join the task (wait for it to complete)
                await task
        """
        return self._loop

    @property
    def disconnected(self: 'TelegramClient') -> asyncio.Future:
        """
        Property with a ``Future`` that resolves upon disconnection.

        Example
            .. code-block:: python

                # Wait for a disconnection to occur
                try:
                    await client.disconnected
                except OSError:
                    print('Error on disconnect')
        """
        return self._sender.disconnected

    # endregion

    # region Connecting

    async def connect(self: 'TelegramClient') -> None:
        """
        Connects to Telegram.

        .. note::

            Connect means connect and nothing else, and only one low-level
            request is made to notify Telegram about which layer we will be
            using.

            Before Telegram sends you updates, you need to make a high-level
            request, like `client.get_me() <telethon.client.users.UserMethods.get_me>`,
            as described in https://core.telegram.org/api/updates.

        Example
            .. code-block:: python

                try:
                    client.connect()
                except OSError:
                    print('Failed to connect')
        """
        await self._sender.connect(self._connection(
            self.session.server_address,
            self.session.port,
            self.session.dc_id,
            loop=self._loop,
            loggers=self._log,
            proxy=self._proxy
        ))
        self.session.auth_key = self._sender.auth_key
        self.session.save()

        await self._sender.send(self._init_with(
            functions.help.GetConfigRequest()))

        self._updates_handle = self._loop.create_task(self._update_loop())

    def is_connected(self: 'TelegramClient') -> bool:
        """
        Returns ``True`` if the user has connected.

        This method is **not** asynchronous (don't use ``await`` on it).

        Example
            .. code-block:: python

                while client.is_connected():
                    await asyncio.sleep(1)
        """
        sender = getattr(self, '_sender', None)
        return sender and sender.is_connected()

    def disconnect(self: 'TelegramClient'):
        """
        Disconnects from Telegram.

        If the event loop is already running, this method returns a
        coroutine that you should await on your own code; otherwise
        the loop is ran until said coroutine completes.

        Example
            .. code-block:: python

                # You don't need to use this if you used "with client"
                client.disconnect()
        """
        if self._loop.is_running():
            return self._disconnect_coro()
        else:
            try:
                self._loop.run_until_complete(self._disconnect_coro())
            except RuntimeError:
                # Python 3.5.x complains when called from
                # `__aexit__` and there were pending updates with:
                #   "Event loop stopped before Future completed."
                #
                # However, it doesn't really make a lot of sense.
                pass

    async def _disconnect_coro(self: 'TelegramClient'):
        await self._disconnect()

        # trio's nurseries would handle this for us, but this is asyncio.
        # All tasks spawned in the background should properly be terminated.
        if self._dispatching_updates_queue is None and self._updates_queue:
            for task in self._updates_queue:
                task.cancel()

            await asyncio.wait(self._updates_queue, loop=self._loop)
            self._updates_queue.clear()

        pts, date = self._state_cache[None]
        if pts and date:
            self.session.set_update_state(0, types.updates.State(
                pts=pts,
                qts=0,
                date=date,
                seq=0,
                unread_count=0
            ))

        self.session.close()

    async def _disconnect(self: 'TelegramClient'):
        """
        Disconnect only, without closing the session. Used in reconnections
        to different data centers, where we don't want to close the session
        file; user disconnects however should close it since it means that
        their job with the client is complete and we should clean it up all.
        """
        await self._sender.disconnect()
        await helpers._cancel(self._log[__name__],
                              updates_handle=self._updates_handle)

    async def _switch_dc(self: 'TelegramClient', new_dc):
        """
        Permanently switches the current connection to the new data center.
        """
        self._log[__name__].info('Reconnecting to new data center %s', new_dc)
        dc = await self._get_dc(new_dc)

        self.session.set_dc(dc.id, dc.ip_address, dc.port)
        # auth_key's are associated with a server, which has now changed
        # so it's not valid anymore. Set to None to force recreating it.
        self._sender.auth_key.key = None
        self.session.auth_key = None
        self.session.save()
        await self._disconnect()
        return await self.connect()

    def _auth_key_callback(self: 'TelegramClient', auth_key):
        """
        Callback from the sender whenever it needed to generate a
        new authorization key. This means we are not authorized.
        """
        self.session.auth_key = auth_key
        self.session.save()

    # endregion

    # region Working with different connections/Data Centers

    async def _get_dc(self: 'TelegramClient', dc_id, cdn=False):
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

    async def _create_exported_sender(self: 'TelegramClient', dc_id):
        """
        Creates a new exported `MTProtoSender` for the given `dc_id` and
        returns it. This method should be used by `_borrow_exported_sender`.
        """
        # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
        # for clearly showing how to export the authorization
        dc = await self._get_dc(dc_id)
        # Can't reuse self._sender._connection as it has its own seqno.
        #
        # If one were to do that, Telegram would reset the connection
        # with no further clues.
        sender = MTProtoSender(None, self._loop, loggers=self._log)
        await sender.connect(self._connection(
            dc.ip_address,
            dc.port,
            dc.id,
            loop=self._loop,
            loggers=self._log,
            proxy=self._proxy
        ))
        self._log[__name__].info('Exporting authorization for data center %s',
                                 dc)
        auth = await self(functions.auth.ExportAuthorizationRequest(dc_id))
        req = self._init_with(functions.auth.ImportAuthorizationRequest(
            id=auth.id, bytes=auth.bytes
        ))
        await sender.send(req)
        return sender

    async def _borrow_exported_sender(self: 'TelegramClient', dc_id):
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
                await sender.connect(self._connection(
                    dc.ip_address,
                    dc.port,
                    dc.id,
                    loop=self._loop,
                    loggers=self._log,
                    proxy=self._proxy
                ))

            self._borrowed_senders[dc_id] = (n + 1, sender)

        return sender

    async def _return_exported_sender(self: 'TelegramClient', sender):
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
                self._log[__name__].info(
                    'Disconnecting borrowed sender for DC %d', dc_id)
                await sender.disconnect()

    async def _get_cdn_client(self: 'TelegramClient', cdn_redirect):
        """Similar to ._borrow_exported_client, but for CDNs"""
        # TODO Implement
        raise NotImplementedError
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = self.session.clone()
            await session.set_dc(dc.id, dc.ip_address, dc.port)
            self._exported_sessions[cdn_redirect.dc_id] = session

        self._log[__name__].info('Creating new CDN client')
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
        return client

    # endregion

    # region Invoking Telegram requests

    @abc.abstractmethod
    def __call__(self: 'TelegramClient', request, ordered=False):
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
    def _handle_update(self: 'TelegramClient', update):
        raise NotImplementedError

    @abc.abstractmethod
    def _update_loop(self: 'TelegramClient'):
        raise NotImplementedError

    @abc.abstractmethod
    async def _handle_auto_reconnect(self: 'TelegramClient'):
        raise NotImplementedError

    # endregion
