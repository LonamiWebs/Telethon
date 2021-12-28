import abc
import re
import asyncio
import collections
import logging
import platform
import time
import typing
import ipaddress

from .. import version, __name__ as __base_name__, _tl
from .._crypto import rsa
from .._misc import markdown, entitycache, statecache, enums, helpers
from .._network import MTProtoSender, Connection, ConnectionTcpFull, connection as conns
from .._sessions import Session, SQLiteSession, MemorySession
from .._sessions.types import DataCenter, SessionState

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


def init(
        self: 'TelegramClient',
        session: 'typing.Union[str, Session]',
        api_id: int,
        api_hash: str,
        *,
        connection: 'typing.Type[Connection]' = ConnectionTcpFull,
        use_ipv6: bool = False,
        proxy: typing.Union[tuple, dict] = None,
        local_addr: typing.Union[str, tuple] = None,
        default_dc_id: int = None,
        default_ipv4_ip: str = None,
        default_ipv6_ip: str = None,
        default_port: int = None,
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
        receive_updates: bool = True
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
    if isinstance(session, str) or session is None:
        try:
            session = SQLiteSession(session)
        except ImportError:
            import warnings
            warnings.warn(
                'The sqlite3 module is not available under this '
                'Python installation and no _ session '
                'instance was given; using MemorySession.\n'
                'You will need to re-login every time unless '
                'you use another session storage'
            )
            session = MemorySession()
    elif not isinstance(session, Session):
        raise TypeError(
            'The given session must be a str or a Session instance.'
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

    # Cache session data for convenient access
    self._session_state = None
    self._all_dcs = None
    self._state_cache = statecache.StateCache(None, self._log)

    self._entity_cache = entitycache.EntityCache()
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

    self._default_dc_id = default_dc_id or DEFAULT_DC_ID
    if not isinstance(self._default_dc_id, int):
        raise TypeError('`default_dc_id` must be an int or None.')
    self._default_ipv4_ip = int(ipaddress.ip_address(default_ipv4_ip or DEFAULT_IPV4_IP))
    self._default_ipv6_ip = int(ipaddress.ip_address(default_ipv6_ip or DEFAULT_IPV6_IP))
    self._default_port = default_port or DEFAULT_PORT
    if not isinstance(self._default_port, int):
        raise TypeError('`default_port` must be an int or None')

    self._raise_last_call_error = raise_last_call_error

    self._request_retries = request_retries
    self._connection_retries = connection_retries
    self._retry_delay = retry_delay or 0
    self._proxy = proxy
    self._local_addr = local_addr
    self._timeout = timeout
    self._auto_reconnect = auto_reconnect

    if connection == ():
        # For now the current default remains TCP Full; may change to be "smart" if proxies are specified
        connection = enums.ConnectionMode.FULL

    self._connection = {
        enums.ConnectionMode.FULL: conns.ConnectionTcpFull,
        enums.ConnectionMode.INTERMEDIATE: conns.ConnectionTcpIntermediate,
        enums.ConnectionMode.ABRIDGED: conns.ConnectionTcpAbridged,
        enums.ConnectionMode.OBFUSCATED: conns.ConnectionTcpObfuscated,
        enums.ConnectionMode.HTTP: conns.ConnectionHttp,
    }[enums.parse_conn_mode(connection)]
    init_proxy = None if not issubclass(self._connection, conns.TcpMTProxy) else \
        _tl.InputClientProxy(*self._connection.address_info(proxy))

    # Used on connection. Capture the variables in a lambda since
    # exporting clients need to create this InvokeWithLayer.
    system = platform.uname()

    if system.machine in ('x86_64', 'AMD64'):
        default_device_model = 'PC 64bit'
    elif system.machine in ('i386','i686','x86'):
        default_device_model = 'PC 32bit'
    else:
        default_device_model = system.machine
    default_system_version = re.sub(r'-.+','',system.release)

    self._init_request = _tl.fn.InitConnection(
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

    self._sender = MTProtoSender(
        loggers=self._log,
        retries=self._connection_retries,
        delay=self._retry_delay,
        auto_reconnect=self._auto_reconnect,
        connect_timeout=self._timeout,
        update_callback=self._handle_update,
        auto_reconnect_callback=self._handle_auto_reconnect
    )

    # Remember flood-waited requests to avoid making them again
    self._flood_waited_requests = {}

    # Cache ``{dc_id: (_ExportState, MTProtoSender)}`` for all borrowed senders
    self._borrowed_senders = {}
    self._borrow_sender_lock = asyncio.Lock()

    self._updates_handle = None
    self._last_request = time.time()
    self._channel_pts = {}
    self._no_updates = not receive_updates

    if sequential_updates:
        self._updates_queue = asyncio.Queue()
        self._dispatching_updates_queue = asyncio.Event()
    else:
        # Use a set of pending instead of a queue so we can properly
        # terminate all pending updates on disconnect.
        self._updates_queue = set()
        self._dispatching_updates_queue = None

    self._authorized = None  # None = unknown, False = no, True = yes

    # Some further state for subclasses
    self._event_builders = []

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


def get_loop(self: 'TelegramClient') -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()

def get_flood_sleep_threshold(self):
    return self._flood_sleep_threshold

def set_flood_sleep_threshold(self, value):
    # None -> 0, negative values don't really matter
    self._flood_sleep_threshold = min(value or 0, 24 * 60 * 60)


async def connect(self: 'TelegramClient') -> None:
    self._all_dcs = {dc.id: dc for dc in await self.session.get_all_dc()}
    self._session_state = await self.session.get_state()

    if self._session_state is None:
        try_fetch_user = False
        self._session_state = SessionState(
            user_id=0,
            dc_id=self._default_dc_id,
            bot=False,
            pts=0,
            qts=0,
            date=0,
            seq=0,
            takeout_id=None,
        )
    else:
        try_fetch_user = self._session_state.user_id == 0

    dc = self._all_dcs.get(self._session_state.dc_id)
    if dc is None:
        dc = DataCenter(
            id=self._default_dc_id,
            ipv4=None if self._use_ipv6 else self._default_ipv4_ip,
            ipv6=self._default_ipv6_ip if self._use_ipv6 else None,
            port=self._default_port,
            auth=b'',
        )
        self._all_dcs[dc.id] = dc

    # Update state (for catching up after a disconnection)
    # TODO Get state from channels too
    self._state_cache = statecache.StateCache(self._session_state, self._log)

    # Use known key, if any
    self._sender.auth_key.key = dc.auth

    if not await self._sender.connect(self._connection(
        str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
        dc.port,
        dc.id,
        loggers=self._log,
        proxy=self._proxy,
        local_addr=self._local_addr
    )):
        # We don't want to init or modify anything if we were already connected
        return

    if self._sender.auth_key.key != dc.auth:
        dc.auth = self._sender.auth_key.key

    # Need to send invokeWithLayer for things to work out.
    # Make the most out of this opportunity by also refreshing our state.
    # During the v1 to v2 migration, this also correctly sets the IPv* columns.
    self._init_request.query = _tl.fn.help.GetConfig()

    config = await self._sender.send(_tl.fn.InvokeWithLayer(
        _tl.LAYER, self._init_request
    ))

    for dc in config.dc_options:
        if dc.media_only or dc.tcpo_only or dc.cdn:
            continue

        ip = int(ipaddress.ip_address(dc.ip_address))
        if dc.id in self._all_dcs:
            self._all_dcs[dc.id].port = dc.port
            if dc.ipv6:
                self._all_dcs[dc.id].ipv6 = ip
            else:
                self._all_dcs[dc.id].ipv4 = ip
        elif dc.ipv6:
            self._all_dcs[dc.id] = DataCenter(dc.id, None, ip, dc.port, b'')
        else:
            self._all_dcs[dc.id] = DataCenter(dc.id, ip, None, dc.port, b'')

    for dc in self._all_dcs.values():
        await self.session.insert_dc(dc)

    if try_fetch_user:
        # If there was a previous session state, but the current user ID is 0, it means we've
        # migrated and not yet populated the current user (or the client connected but never
        # logged in). Attempt to fetch the user now. If it works, also get the update state.
        me = await self.get_me()
        if me:
            await self._update_session_state(me, save=False)

    await self.session.save()

    self._updates_handle = self.loop.create_task(self._update_loop())

def is_connected(self: 'TelegramClient') -> bool:
    sender = getattr(self, '_sender', None)
    return sender and sender.is_connected()

async def disconnect(self: 'TelegramClient'):
    return await _disconnect_coro(self)

def set_proxy(self: 'TelegramClient', proxy: typing.Union[tuple, dict]):
    init_proxy = None if not issubclass(self._connection, conns.TcpMTProxy) else \
        _tl.InputClientProxy(*self._connection.address_info(proxy))

    self._init_request.proxy = init_proxy
    self._proxy = proxy

    # While `await client.connect()` passes new proxy on each new call,
    # auto-reconnect attempts use already set up `_connection` inside
    # the `_sender`, so the only way to change proxy between those
    # is to directly inject parameters.

    connection = getattr(self._sender, "_connection", None)
    if connection:
        if isinstance(connection, conns.TcpMTProxy):
            connection._ip = proxy[0]
            connection._port = proxy[1]
        else:
            connection._proxy = proxy

async def _disconnect_coro(self: 'TelegramClient'):
    await _disconnect(self)

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
    if self._dispatching_updates_queue is None and self._updates_queue:
        for task in self._updates_queue:
            task.cancel()

        await asyncio.wait(self._updates_queue)
        self._updates_queue.clear()

    pts, date = self._state_cache[None]
    if pts and date:
        if self._session_state:
            self._session_state.pts = pts
            self._session_state.date = date
            await self.session.set_state(self._session_state)
            await self.session.save()

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

    self._session_state.dc_id = new_dc
    await self.session.set_state(self._session_state)
    await self.session.save()

    await _disconnect(self)
    return await self.connect()

async def _create_exported_sender(self: 'TelegramClient', dc_id):
    """
    Creates a new exported `MTProtoSender` for the given `dc_id` and
    returns it. This method should be used by `_borrow_exported_sender`.
    """
    # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
    # for clearly showing how to export the authorization
    dc = self._all_dcs[dc_id]
    # Can't reuse self._sender._connection as it has its own seqno.
    #
    # If one were to do that, Telegram would reset the connection
    # with no further clues.
    sender = MTProtoSender(loggers=self._log)
    await sender.connect(self._connection(
        str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
        dc.port,
        dc.id,
        loggers=self._log,
        proxy=self._proxy,
        local_addr=self._local_addr
    ))
    self._log[__name__].info('Exporting auth for new borrowed sender in %s', dc)
    auth = await self(_tl.fn.auth.ExportAuthorization(dc_id))
    self._init_request.query = _tl.fn.auth.ImportAuthorization(id=auth.id, bytes=auth.bytes)
    req = _tl.fn.InvokeWithLayer(_tl.LAYER, self._init_request)
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
            sender = await _create_exported_sender(self, dc_id)
            sender.dc_id = dc_id
            self._borrowed_senders[dc_id] = (state, sender)

        elif state.need_connect():
            dc = self._all_dcs[dc_id]
            await sender.connect(self._connection(
                str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
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
