import abc
import re
import asyncio
import collections
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
from ..tl import functions, types
from ..tl.alltlobjects import LAYER

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

    self._sender = MTProtoSender(
        self.session.auth_key,
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

    # Update state (for catching up after a disconnection)
    # TODO Get state from channels too
    self._state_cache = StateCache(
        self.session.get_update_state(0), self._log)

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

    # Sometimes we need to know who we are, cache the self peer
    self._self_input_peer = None
    self._bot = None

    # A place to store if channels are a megagroup or not (see `edit_admin`)
    self._megagroup_cache = {}


def get_loop(self: 'TelegramClient') -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()

def get_disconnected(self: 'TelegramClient') -> asyncio.Future:
    return self._sender.disconnected

def get_flood_sleep_threshold(self):
    return self._flood_sleep_threshold

def set_flood_sleep_threshold(self, value):
    # None -> 0, negative values don't really matter
    self._flood_sleep_threshold = min(value or 0, 24 * 60 * 60)


async def connect(self: 'TelegramClient') -> None:
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

    self._init_request.query = functions.help.GetConfigRequest()

    await self._sender.send(functions.InvokeWithLayerRequest(
        LAYER, self._init_request
    ))

    self._updates_handle = self.loop.create_task(self._update_loop())

def is_connected(self: 'TelegramClient') -> bool:
    sender = getattr(self, '_sender', None)
    return sender and sender.is_connected()

def disconnect(self: 'TelegramClient'):
    if self.loop.is_running():
        return self._disconnect_coro()
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

async def _disconnect_coro(self: 'TelegramClient'):
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
    if self._dispatching_updates_queue is None and self._updates_queue:
        for task in self._updates_queue:
            task.cancel()

        await asyncio.wait(self._updates_queue)
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


async def _get_dc(self: 'TelegramClient', dc_id, cdn=False):
    """Gets the Data Center (DC) associated to 'dc_id'"""
    cls = self.__class__
    if not cls._config:
        cls._config = await self(functions.help.GetConfigRequest())

    if cdn and not self._cdn_config:
        cls._cdn_config = await self(functions.help.GetCdnConfigRequest())
        for pk in cls._cdn_config.public_keys:
            rsa.add_key(pk.public_key)

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
        return next(
            dc for dc in cls._config.dc_options
            if dc.id == dc_id and bool(dc.cdn) == cdn
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
    # TODO Implement
    raise NotImplementedError
    session = self._exported_sessions.get(cdn_redirect.dc_id)
    if not session:
        dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
        session = self.session.clone()
        await session.set_dc(dc.id, dc.ip_address, dc.port)
        self._exported_sessions[cdn_redirect.dc_id] = session

    self._log[__name__].info('Creating new CDN client')
    client = TelegramBaseClient(
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


@abc.abstractmethod
def __call__(self: 'TelegramClient', request, ordered=False):
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
