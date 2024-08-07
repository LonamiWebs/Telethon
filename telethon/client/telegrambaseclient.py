import abc
import re
import asyncio
import collections
import logging
import platform
import time
import typing
import datetime
import pathlib

from .. import version, helpers, __name__ as __base_name__
from ..crypto import rsa
from ..extensions import markdown
from ..network import MTProtoSender, Connection, ConnectionTcpFull, TcpMTProxy
from ..sessions import Session, SQLiteSession, MemorySession
from ..tl import functions, types
from ..tl.alltlobjects import LAYER
from .._updates import MessageBox, EntityCache as MbEntityCache, SessionState, ChannelState, Entity, EntityType

DEFAULT_DC_ID = 2
DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '2001:67c:4e8:f002::a'
DEFAULT_PORT = 443

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient

_base_log = logging.getLogger(__base_name__)


# In seconds, how long to wait before disconnecting a exported sender.
_DISCONNECT_EXPORTED_AFTER = 60


class _ExportState:
    def __init__(self):
        # ``n`` is the amount of borrows a given sender has;
        # once ``n`` reaches ``0``, disconnect the sender after a while.
        self._n = 0
        self._zero_ts = 0
        self._connected = False

    def add_borrow(self):
        self._n += 1
        self._connected = True

    def add_return(self):
        self._n -= 1
        assert self._n >= 0, 'returned sender more than it was borrowed'
        if self._n == 0:
            self._zero_ts = time.time()

    def should_disconnect(self):
        return (self._n == 0
                and self._connected
                and (time.time() - self._zero_ts) > _DISCONNECT_EXPORTED_AFTER)

    def need_connect(self):
        return not self._connected

    def mark_disconnected(self):
        assert self.should_disconnect(), 'marked as disconnected when it was borrowed'
        self._connected = False


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
            used otherwise. If it's `None`, the session will not be saved,
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
            The API hash you obtained from https://my.telegram.org.

        connection (`telethon.network.connection.common.Connection`, optional):
            The connection instance to be used when creating a new connection
            to the servers. It **must** be a type.

            Defaults to `telethon.network.connection.tcpfull.ConnectionTcpFull`.

        use_ipv6 (`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is `False` as IPv6 support is not
            too widespread yet.

        proxy (`tuple` | `list` | `dict`, optional):
            An iterable consisting of the proxy info. If `connection` is
            one of `MTProxy`, then it should contain MTProxy credentials:
            ``('hostname', port, 'secret')``. Otherwise, it's meant to store
            function parameters for PySocks, like ``(type, 'hostname', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        local_addr (`str` | `tuple`, optional):
            Local host address (and port, optionally) used to bind the socket to locally.
            You only need to use this if you have multiple network cards and
            want to use a specific one.

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

            May take a negative or `None` value for infinite retries, but
            this is not recommended, since some requests can always trigger
            a call fail (such as searching for messages).

        connection_retries (`int` | `None`, optional):
            How many times the reconnection should retry, either on the
            initial connection or when Telegram disconnects us. May be
            set to a negative or `None` value for infinite retries, but
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

            If set to `True`, incoming updates will be put in a queue
            and processed sequentially. This means your event handlers
            should *not* perform long-running operations since new
            updates are put inside of an unbounded queue.

        flood_sleep_threshold (`int` | `float`, optional):
            The threshold below which the library should automatically
            sleep on flood wait and slow mode wait errors (inclusive). For instance, if a
            ``FloodWaitError`` for 17s occurs and `flood_sleep_threshold`
            is 20s, the library will ``sleep`` automatically. If the error
            was for 21s, it would ``raise FloodWaitError`` instead. Values
            larger than a day (like ``float('inf')``) will be changed to a day.

        raise_last_call_error (`bool`, optional):
            When API calls fail in a way that causes Telethon to retry
            automatically, should the RPC error of the last attempt be raised
            instead of a generic ValueError. This is mostly useful for
            detecting when Telegram has internal issues.

        device_model (`str`, optional):
            "Device model" to be sent when creating the initial connection.
            Defaults to 'PC (n)bit' derived from ``platform.uname().machine``, or its direct value if unknown.

        system_version (`str`, optional):
            "System version" to be sent when creating the initial connection.
            Defaults to ``platform.uname().release`` stripped of everything ahead of -.

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
            Asyncio event loop to use. Defaults to `asyncio.get_running_loop()`.
            This argument is ignored.

        base_logger (`str` | `logging.Logger`, optional):
            Base logger name or instance to use.
            If a `str` is given, it'll be passed to `logging.getLogger()`. If a
            `logging.Logger` is given, it'll be used directly. If something
            else or nothing is given, the default logger will be used.

        receive_updates (`bool`, optional):
            Whether the client will receive updates or not. By default, updates
            will be received from Telegram as they occur.

            Turning this off means that Telegram will not send updates at all
            so event handlers, conversations, and QR login will not work.
            However, certain scripts don't need updates, so this will reduce
            the amount of bandwidth used.

        entity_cache_limit (`int`, optional):
            How many users, chats and channels to keep in the in-memory cache
            at most. This limit is checked against when processing updates.

            When this limit is reached or exceeded, all entities that are not
            required for update handling will be flushed to the session file.

            Note that this implies that there is a lower bound to the amount
            of entities that must be kept in memory.

            Setting this limit too low will cause the library to attempt to
            flush entities to the session file even if no entities can be
            removed from the in-memory cache, which will degrade performance.
    """

    # Current TelegramClient version
    __version__ = version.__version__

    # Cached server configuration (with .dc_options), can be "global"
    _config = None
    _cdn_config = None

    # region Initialization

    def __init__(
            self: 'TelegramClient',
            session: 'typing.Union[str, pathlib.Path, Session]',
            api_id: int,
            api_hash: str,
            *,
            connection: 'typing.Type[Connection]' = ConnectionTcpFull,
            use_ipv6: bool = False,
            proxy: typing.Union[tuple, dict] = None,
            local_addr: typing.Union[str, tuple] = None,
            timeout: int = 10,
            request_retries: int = 5,
            connection_retries: int = 5,
            retry_delay: int = 1,
            auto_reconnect: bool = True,
            sequential_updates: bool = False,
            flood_sleep_threshold: int = 60,
            raise_last_call_error: bool = False,
            device_model: str = None,
            system_version: str = None,
            app_version: str = None,
            lang_code: str = 'en',
            system_lang_code: str = 'en',
            loop: asyncio.AbstractEventLoop = None,
            base_logger: typing.Union[str, logging.Logger] = None,
            receive_updates: bool = True,
            catch_up: bool = False,
            entity_cache_limit: int = 5000
    ):
        if not api_id or not api_hash:
            raise ValueError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to telethon.rtfd.io for more information.")

        self._use_ipv6 = use_ipv6

        if isinstance(base_logger, str):
            base_logger = logging.getLogger(base_logger)
        elif not isinstance(base_logger, logging.Logger):
            base_logger = _base_log

        class _Loggers(dict):
            def __missing__(self, key):
                if key.startswith("telethon."):
                    key = key.split('.', maxsplit=1)[1]

                return base_logger.getChild(key)

        self._log = _Loggers()

        # Determine what session object we have
        if isinstance(session, (str, pathlib.Path)):
            try:
                session = SQLiteSession(str(session))
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
        elif session is None:
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
        # ChatGetter and SenderGetter can use the in-memory _mb_entity_cache
        # to avoid network access and the need for await in session files.
        #
        # The session files only wants the entities to persist
        # them to disk, and to save additional useful information.
        # TODO Session should probably return all cached
        #      info of entities, not just the input versions
        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash

        # Current proxy implementation requires `sock_connect`, and some
        # event loops lack this method. If the current loop is missing it,
        # bail out early and suggest an alternative.
        #
        # TODO A better fix is obviously avoiding the use of `sock_connect`
        #
        # See https://github.com/LonamiWebs/Telethon/issues/1337 for details.
        if not callable(getattr(self.loop, 'sock_connect', None)):
            raise TypeError(
                'Event loop of type {} lacks `sock_connect`, which is needed to use proxies.\n\n'
                'Change the event loop in use to use proxies:\n'
                '# https://github.com/LonamiWebs/Telethon/issues/1337\n'
                'import asyncio\n'
                'asyncio.set_event_loop(asyncio.SelectorEventLoop())'.format(
                    self.loop.__class__.__name__
                )
            )

        if local_addr is not None:
            if use_ipv6 is False and ':' in local_addr:
                raise TypeError(
                    'A local IPv6 address must only be used with `use_ipv6=True`.'
                )
            elif use_ipv6 is True and ':' not in local_addr:
                raise TypeError(
                    '`use_ipv6=True` must only be used with a local IPv6 address.'
                )

        self._raise_last_call_error = raise_last_call_error

        self._request_retries = request_retries
        self._connection_retries = connection_retries
        self._retry_delay = retry_delay or 0
        self._proxy = proxy
        self._local_addr = local_addr
        self._timeout = timeout
        self._auto_reconnect = auto_reconnect

        assert isinstance(connection, type)
        self._connection = connection
        init_proxy = None if not issubclass(connection, TcpMTProxy) else \
            types.InputClientProxy(*connection.address_info(proxy))

        # Used on connection. Capture the variables in a lambda since
        # exporting clients need to create this InvokeWithLayerRequest.
        system = platform.uname()

        if system.machine in ('x86_64', 'AMD64'):
            default_device_model = 'PC 64bit'
        elif system.machine in ('i386','i686','x86'):
            default_device_model = 'PC 32bit'
        else:
            default_device_model = system.machine
        default_system_version = re.sub(r'-.+','',system.release)

        self._init_request = functions.InitConnectionRequest(
            api_id=self.api_id,
            device_model=device_model or default_device_model or 'Unknown',
            system_version=system_version or default_system_version or '1.0',
            app_version=app_version or self.__version__,
            lang_code=lang_code,
            system_lang_code=system_lang_code,
            lang_pack='',  # "langPacks are for official apps only"
            query=None,
            proxy=init_proxy
        )

        # Remember flood-waited requests to avoid making them again
        self._flood_waited_requests = {}

        # Cache ``{dc_id: (_ExportState, MTProtoSender)}`` for all borrowed senders
        self._borrowed_senders = {}
        self._borrow_sender_lock = asyncio.Lock()
        self._exported_sessions = {}

        self._loop = None  # only used as a sanity check
        self._updates_error = None
        self._updates_handle = None
        self._keepalive_handle = None
        self._last_request = time.time()
        self._no_updates = not receive_updates

        # Used for non-sequential updates, in order to terminate all pending tasks on disconnect.
        self._sequential_updates = sequential_updates
        self._event_handler_tasks = set()

        self._authorized = None  # None = unknown, False = no, True = yes

        # Some further state for subclasses
        self._event_builders = []

        # {chat_id: {Conversation}}
        self._conversations = collections.defaultdict(set)

        # Hack to workaround the fact Telegram may send album updates as
        # different Updates when being sent from a different data center.
        # {grouped_id: AlbumHack}
        #
        # FIXME: We don't bother cleaning this up because it's not really
        #        worth it, albums are pretty rare and this only holds them
        #        for a second at most.
        self._albums = {}

        # Default parse mode
        self._parse_mode = markdown

        # Some fields to easy signing in. Let {phone: hash} be
        # a dictionary because the user may change their mind.
        self._phone_code_hash = {}
        self._phone = None
        self._tos = None

        # A place to store if channels are a megagroup or not (see `edit_admin`)
        self._megagroup_cache = {}

        # This is backported from v2 in a very ad-hoc way just to get proper update handling
        self._catch_up = catch_up
        self._updates_queue = asyncio.Queue()
        self._message_box = MessageBox(self._log['messagebox'])
        self._mb_entity_cache = MbEntityCache()  # required for proper update handling (to know when to getDifference)
        self._entity_cache_limit = entity_cache_limit

        self._sender = MTProtoSender(
            self.session.auth_key,
            loggers=self._log,
            retries=self._connection_retries,
            delay=self._retry_delay,
            auto_reconnect=self._auto_reconnect,
            connect_timeout=self._timeout,
            auth_key_callback=self._auth_key_callback,
            updates_queue=self._updates_queue,
            auto_reconnect_callback=self._handle_auto_reconnect
        )


    # endregion

    # region Properties

    @property
    def loop(self: 'TelegramClient') -> asyncio.AbstractEventLoop:
        """
        Property with the ``asyncio`` event loop used by this client.

        Example
            .. code-block:: python

                # Download media in the background
                task = client.loop.create_task(message.download_media())

                # Do some work
                ...

                # Join the task (wait for it to complete)
                await task
        """
        return helpers.get_running_loop()

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

    @property
    def flood_sleep_threshold(self):
        return self._flood_sleep_threshold

    @flood_sleep_threshold.setter
    def flood_sleep_threshold(self, value):
        # None -> 0, negative values don't really matter
        self._flood_sleep_threshold = min(value or 0, 24 * 60 * 60)

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
                    await client.connect()
                except OSError:
                    print('Failed to connect')
        """
        if self.session is None:
            raise ValueError('TelegramClient instance cannot be reused after logging out')

        if self._loop is None:
            self._loop = helpers.get_running_loop()
        elif self._loop != helpers.get_running_loop():
            raise RuntimeError('The asyncio event loop must not change after connection (see the FAQ for details)')

        if not await self._sender.connect(self._connection(
            self.session.server_address,
            self.session.port,
            self.session.dc_id,
            loggers=self._log,
            proxy=self._proxy,
            local_addr=self._local_addr
        )):
            # We don't want to init or modify anything if we were already connected
            return

        self.session.auth_key = self._sender.auth_key
        self.session.save()

        try:
            # See comment when saving entities to understand this hack
            self_id = self.session.get_input_entity(0).access_hash
            self_user = self.session.get_input_entity(self_id)
            self._mb_entity_cache.set_self_user(self_id, None, self_user.access_hash)
        except ValueError:
            pass

        if self._catch_up:
            ss = SessionState(0, 0, False, 0, 0, 0, 0, None)
            cs = []

            for entity_id, state in self.session.get_update_states():
                if entity_id == 0:
                    # TODO current session doesn't store self-user info but adding that is breaking on downstream session impls
                    ss = SessionState(0, 0, False, state.pts, state.qts, int(state.date.timestamp()), state.seq, None)
                else:
                    cs.append(ChannelState(entity_id, state.pts))

            self._message_box.load(ss, cs)
            for state in cs:
                try:
                    entity = self.session.get_input_entity(state.channel_id)
                except ValueError:
                    self._log[__name__].warning(
                        'No access_hash in cache for channel %s, will not catch up', state.channel_id)
                else:
                    self._mb_entity_cache.put(Entity(EntityType.CHANNEL, entity.channel_id, entity.access_hash))

        self._init_request.query = functions.help.GetConfigRequest()

        req = self._init_request
        if self._no_updates:
            req = functions.InvokeWithoutUpdatesRequest(req)

        await self._sender.send(functions.InvokeWithLayerRequest(LAYER, req))

        if self._message_box.is_empty():
            me = await self.get_me()
            if me:
                await self._on_login(me)  # also calls GetState to initialize the MessageBox

        self._updates_handle = self.loop.create_task(self._update_loop())
        self._keepalive_handle = self.loop.create_task(self._keepalive_loop())

    def is_connected(self: 'TelegramClient') -> bool:
        """
        Returns `True` if the user has connected.

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

        Event handlers which are currently running will be cancelled before
        this function returns (in order to properly clean-up their tasks).
        In particular, this means that using ``disconnect`` in a handler
        will cause code after the ``disconnect`` to never run. If this is
        needed, consider spawning a separate task to do the remaining work.

        Example
            .. code-block:: python

                # You don't need to use this if you used "with client"
                await client.disconnect()
        """
        if self.loop.is_running():
            # Disconnect may be called from an event handler, which would
            # cancel itself during itself and never actually complete the
            # disconnection. Shield the task to prevent disconnect itself
            # from being cancelled. See issue #3942 for more details.
            return asyncio.shield(self.loop.create_task(self._disconnect_coro()))
        else:
            try:
                self.loop.run_until_complete(self._disconnect_coro())
            except RuntimeError:
                # Python 3.5.x complains when called from
                # `__aexit__` and there were pending updates with:
                #   "Event loop stopped before Future completed."
                #
                # However, it doesn't really make a lot of sense.
                pass

    def set_proxy(self: 'TelegramClient', proxy: typing.Union[tuple, dict]):
        """
        Changes the proxy which will be used on next (re)connection.

        Method has no immediate effects if the client is currently connected.

        The new proxy will take it's effect on the next reconnection attempt:
            - on a call `await client.connect()` (after complete disconnect)
            - on auto-reconnect attempt (e.g, after previous connection was lost)
        """
        init_proxy = None if not issubclass(self._connection, TcpMTProxy) else \
            types.InputClientProxy(*self._connection.address_info(proxy))

        self._init_request.proxy = init_proxy
        self._proxy = proxy

        # While `await client.connect()` passes new proxy on each new call,
        # auto-reconnect attempts use already set up `_connection` inside
        # the `_sender`, so the only way to change proxy between those
        # is to directly inject parameters.

        connection = getattr(self._sender, "_connection", None)
        if connection:
            if isinstance(connection, TcpMTProxy):
                connection._ip = proxy[0]
                connection._port = proxy[1]
            else:
                connection._proxy = proxy

    def _save_states_and_entities(self: 'TelegramClient'):
        entities = self._mb_entity_cache.get_all_entities()

        # Piggy-back on an arbitrary TL type with users and chats so the session can understand to read the entities.
        # It doesn't matter if we put users in the list of chats.
        self.session.process_entities(types.contacts.ResolvedPeer(None, [e._as_input_peer() for e in entities], []))

        # As a hack to not need to change the session files, save ourselves with ``id=0`` and ``access_hash`` of our ``id``.
        # This way it is possible to determine our own ID by querying for 0. However, whether we're a bot is not saved.
        if self._mb_entity_cache.self_id:
            self.session.process_entities(types.contacts.ResolvedPeer(None, [types.InputPeerUser(0, self._mb_entity_cache.self_id)], []))

        ss, cs = self._message_box.session_state()
        self.session.set_update_state(0, types.updates.State(**ss, unread_count=0))
        now = datetime.datetime.now()  # any datetime works; channels don't need it
        for channel_id, pts in cs.items():
            self.session.set_update_state(channel_id, types.updates.State(pts, 0, now, 0, unread_count=0))

    async def _disconnect_coro(self: 'TelegramClient'):
        if self.session is None:
            return  # already logged out and disconnected

        await self._disconnect()

        # Also clean-up all exported senders because we're done with them
        async with self._borrow_sender_lock:
            for state, sender in self._borrowed_senders.values():
                # Note that we're not checking for `state.should_disconnect()`.
                # If the user wants to disconnect the client, ALL connections
                # to Telegram (including exported senders) should be closed.
                #
                # Disconnect should never raise, so there's no try/except.
                await sender.disconnect()
                # Can't use `mark_disconnected` because it may be borrowed.
                state._connected = False

            # If any was borrowed
            self._borrowed_senders.clear()

        # trio's nurseries would handle this for us, but this is asyncio.
        # All tasks spawned in the background should properly be terminated.
        if self._event_handler_tasks:
            for task in self._event_handler_tasks:
                task.cancel()

            await asyncio.wait(self._event_handler_tasks)
            self._event_handler_tasks.clear()

        self._save_states_and_entities()

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
                              updates_handle=self._updates_handle,
                              keepalive_handle=self._keepalive_handle)

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
                if pk.dc_id == dc_id:
                    rsa.add_key(pk.public_key, old=False)

        try:
            return next(
                dc for dc in cls._config.dc_options
                if dc.id == dc_id
                and bool(dc.ipv6) == self._use_ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            self._log[__name__].warning(
                'Failed to get DC %s (cdn = %s) with use_ipv6 = %s; retrying ignoring IPv6 check',
                dc_id, cdn, self._use_ipv6
            )
            try:
                return next(
                    dc for dc in cls._config.dc_options
                    if dc.id == dc_id and bool(dc.cdn) == cdn
                )
            except StopIteration:
                raise ValueError(f'Failed to get DC {dc_id} (cdn = {cdn})')

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
        sender = MTProtoSender(None, loggers=self._log)
        await sender.connect(self._connection(
            dc.ip_address,
            dc.port,
            dc.id,
            loggers=self._log,
            proxy=self._proxy,
            local_addr=self._local_addr
        ))
        self._log[__name__].info('Exporting auth for new borrowed sender in %s', dc)
        auth = await self(functions.auth.ExportAuthorizationRequest(dc_id))
        self._init_request.query = functions.auth.ImportAuthorizationRequest(id=auth.id, bytes=auth.bytes)
        req = functions.InvokeWithLayerRequest(LAYER, self._init_request)
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
            self._log[__name__].debug('Borrowing sender for dc_id %d', dc_id)
            state, sender = self._borrowed_senders.get(dc_id, (None, None))

            if state is None:
                state = _ExportState()
                sender = await self._create_exported_sender(dc_id)
                sender.dc_id = dc_id
                self._borrowed_senders[dc_id] = (state, sender)

            elif state.need_connect():
                dc = await self._get_dc(dc_id)
                await sender.connect(self._connection(
                    dc.ip_address,
                    dc.port,
                    dc.id,
                    loggers=self._log,
                    proxy=self._proxy,
                    local_addr=self._local_addr
                ))

            state.add_borrow()
            return sender

    async def _return_exported_sender(self: 'TelegramClient', sender):
        """
        Returns a borrowed exported sender. If all borrows have
        been returned, the sender is cleanly disconnected.
        """
        async with self._borrow_sender_lock:
            self._log[__name__].debug('Returning borrowed sender for dc_id %d', sender.dc_id)
            state, _ = self._borrowed_senders[sender.dc_id]
            state.add_return()

    async def _clean_exported_senders(self: 'TelegramClient'):
        """
        Cleans-up all unused exported senders by disconnecting them.
        """
        async with self._borrow_sender_lock:
            for dc_id, (state, sender) in self._borrowed_senders.items():
                if state.should_disconnect():
                    self._log[__name__].info(
                        'Disconnecting borrowed sender for DC %d', dc_id)

                    # Disconnect should never raise
                    await sender.disconnect()
                    state.mark_disconnected()

    async def _get_cdn_client(self: 'TelegramClient', cdn_redirect):
        """Similar to ._borrow_exported_client, but for CDNs"""
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = self.session.clone()
            session.set_dc(dc.id, dc.ip_address, dc.port)
            self._exported_sessions[cdn_redirect.dc_id] = session

        self._log[__name__].info('Creating new CDN client')
        client = self.__class__(
            session, self.api_id, self.api_hash,
            proxy=self._proxy,
            timeout=self._timeout,
            loop=self.loop
        )

        session.auth_key = self._sender.auth_key
        await client._sender.connect(self._connection(
            session.server_address,
            session.port,
            session.dc_id,
            loggers=self._log,
            proxy=self._proxy,
            local_addr=self._local_addr
        ))
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

            flood_sleep_threshold (`int` | `None`, optional):
                The flood sleep threshold to use for this request. This overrides
                the default value stored in
                `client.flood_sleep_threshold <telethon.client.telegrambaseclient.TelegramBaseClient.flood_sleep_threshold>`

        Returns:
            The result of the request (often a `TLObject`) or a list of
            results if more than one request was given.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _update_loop(self: 'TelegramClient'):
        raise NotImplementedError

    @abc.abstractmethod
    async def _handle_auto_reconnect(self: 'TelegramClient'):
        raise NotImplementedError

    # endregion
