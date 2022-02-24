import abc
import re
import asyncio
import collections
import logging
import platform
import time
import typing
import ipaddress
import dataclasses
import functools

from .. import version, __name__ as __base_name__, _tl
from .._crypto import rsa
from .._misc import markdown, enums, helpers
from .._network import MTProtoSender, Connection, transports
from .._sessions import Session, SQLiteSession, MemorySession
from .._sessions.types import DataCenter, SessionState, EntityType, ChannelState
from .._updates import EntityCache, MessageBox

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
        # Logging.
        base_logger: typing.Union[str, logging.Logger] = None,
        # Connection parameters.
        use_ipv6: bool = False,
        proxy: typing.Union[tuple, dict] = None,
        local_addr: typing.Union[str, tuple] = None,
        device_model: str = None,
        system_version: str = None,
        app_version: str = None,
        lang_code: str = 'en',
        system_lang_code: str = 'en',
        # Nice-to-have.
        auto_reconnect: bool = True,
        connect_timeout: int = 10,
        connect_retries: int = 4,
        connect_retry_delay: int = 1,
        request_retries: int = 4,
        flood_sleep_threshold: int = 60,
        # Update handling.
        catch_up: bool = False,
        receive_updates: bool = True,
        max_queued_updates: int = 100,
):
    # Logging.
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

    # Sessions.
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

    self._session = session
    # In-memory copy of the session's state to avoid a roundtrip as it contains commonly-accessed values.
    self._session_state = _default_session_state()

    # Nice-to-have.
    self._request_retries = request_retries
    self._connect_retries = connect_retries
    self._connect_retry_delay = connect_retry_delay or 0
    self._connect_timeout = connect_timeout
    self.flood_sleep_threshold = flood_sleep_threshold
    self._flood_waited_requests = {}  # prevent calls that would floodwait entirely
    self._phone_code_hash = None  # used during login to prevent exposing the hash to end users
    self._tos = None  # used during signup and when fetching tos (tos/expiry)

    # Update handling.
    self._catch_up = catch_up
    self._no_updates = not receive_updates
    self._updates_queue = asyncio.Queue(maxsize=max_queued_updates)
    self._updates_handle = None
    self._update_handlers = []  # sorted list
    self._dispatching_update_handlers = False  # while dispatching, if add/remove are called, we need to make a copy
    self._message_box = MessageBox()
    self._entity_cache = EntityCache()  # required for proper update handling (to know when to getDifference)

    # Connection parameters.
    if not api_id or not api_hash:
        raise ValueError(
            "Your API ID or Hash cannot be empty or None. "
            "Refer to docs.telethon.dev for more information.")

    if local_addr is not None:
        if use_ipv6 is False and ':' in local_addr:
            raise TypeError('A local IPv6 address must only be used with `use_ipv6=True`.')
        elif use_ipv6 is True and ':' not in local_addr:
            raise TypeError('`use_ipv6=True` must only be used with a local IPv6 address.')

    self._transport = transports.Full()
    self._use_ipv6 = use_ipv6
    self._local_addr = local_addr
    self._proxy = proxy
    self._auto_reconnect = auto_reconnect
    self._api_id = int(api_id)
    self._api_hash = api_hash

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

    self._init_request = functools.partial(
        _tl.fn.InitConnection,
        api_id=self._api_id,
        device_model=device_model or default_device_model or 'Unknown',
        system_version=system_version or default_system_version or '1.0',
        app_version=app_version or self.__version__,
        lang_code=lang_code,
        system_lang_code=system_lang_code,
        lang_pack='',  # "langPacks are for official apps only"
    )

    self._sender = MTProtoSender(
        loggers=self._log,
        retries=self._connect_retries,
        delay=self._connect_retry_delay,
        auto_reconnect=self._auto_reconnect,
        connect_timeout=self._connect_timeout,
        updates_queue=self._updates_queue,
    )

    # Cache ``{dc_id: (_ExportState, MTProtoSender)}`` for all borrowed senders.
    self._borrowed_senders = {}
    self._borrow_sender_lock = asyncio.Lock()


def get_flood_sleep_threshold(self):
    return self._flood_sleep_threshold

def set_flood_sleep_threshold(self, value):
    # None -> 0, negative values don't really matter
    self._flood_sleep_threshold = min(value or 0, 24 * 60 * 60)


def _default_session_state():
    return SessionState(
        user_id=0,
        dc_id=DEFAULT_DC_ID,
        bot=False,
        pts=0,
        qts=0,
        date=0,
        seq=0,
        takeout_id=None,
    )


async def connect(self: 'TelegramClient') -> None:
    all_dcs = {dc.id: dc for dc in await self._session.get_all_dc()}
    self._session_state = await self._session.get_state()

    if self._session_state is None:
        try_fetch_user = False
        self._session_state = _default_session_state()
    else:
        try_fetch_user = self._session_state.user_id == 0
        if self._catch_up:
            channel_states = await self._session.get_all_channel_states()
            self._message_box.load(self._session_state, channel_states)
            for state in channel_states:
                entity = await self._session.get_entity(EntityType.CHANNEL, state.channel_id)
                if entity:
                    self._entity_cache.put(entity)

    dc = all_dcs.get(self._session_state.dc_id)
    if dc is None:
        dc = DataCenter(
            id=DEFAULT_DC_ID,
            ipv4=None if self._use_ipv6 else int(ipaddress.ip_address(DEFAULT_IPV4_IP)),
            ipv6=int(ipaddress.ip_address(DEFAULT_IPV6_IP)) if self._use_ipv6 else None,
            port=DEFAULT_PORT,
            auth=b'',
        )
        all_dcs[dc.id] = dc

    # Use known key, if any
    self._sender.auth_key.key = dc.auth

    if not await self._sender.connect(Connection(
        ip=str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
        port=dc.port,
        transport=self._transport.recreate_fresh(),
        loggers=self._log,
        local_addr=self._local_addr,
    )):
        # We don't want to init or modify anything if we were already connected
        return

    if self._sender.auth_key.key != dc.auth:
        all_dcs[dc.id] = dc = dataclasses.replace(dc, auth=self._sender.auth_key.key)

    # Need to send invokeWithLayer for things to work out.
    # Make the most out of this opportunity by also refreshing our state.
    # During the v1 to v2 migration, this also correctly sets the IPv* columns.
    config = await self._sender.send(_tl.fn.InvokeWithLayer(
        _tl.LAYER, self._init_request(query=_tl.fn.help.GetConfig())
    ))

    for dc in config.dc_options:
        if dc.media_only or dc.tcpo_only or dc.cdn:
            continue

        ip = int(ipaddress.ip_address(dc.ip_address))
        if dc.id in all_dcs:
            if dc.ipv6:
                all_dcs[dc.id] = dataclasses.replace(all_dcs[dc.id], port=dc.port, ipv6=ip)
            else:
                all_dcs[dc.id] = dataclasses.replace(all_dcs[dc.id], port=dc.port, ipv4=ip)
        elif dc.ipv6:
            all_dcs[dc.id] = DataCenter(dc.id, None, ip, dc.port, b'')
        else:
            all_dcs[dc.id] = DataCenter(dc.id, ip, None, dc.port, b'')

    for dc in all_dcs.values():
        await self._session.insert_dc(dc)

    if try_fetch_user:
        # If there was a previous session state, but the current user ID is 0, it means we've
        # migrated and not yet populated the current user (or the client connected but never
        # logged in). Attempt to fetch the user now. If it works, also get the update state.
        me = await self.get_me()
        if me:
            await self._update_session_state(me, save=False)

    await self._session.save()

    self._updates_handle = asyncio.create_task(self._update_loop())


def is_connected(self: 'TelegramClient') -> bool:
    return self._sender.is_connected()


async def disconnect(self: 'TelegramClient'):
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


def set_proxy(self: 'TelegramClient', proxy: typing.Union[tuple, dict]):
    init_proxy = None

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


async def _disconnect(self: 'TelegramClient'):
    """
    Disconnect only, without closing the session. Used in reconnections
    to different data centers, where we don't want to close the session
    file; user disconnects however should close it since it means that
    their job with the client is complete and we should clean it up all.
    """
    await self._sender.disconnect()
    await helpers._cancel(self._log[__name__], updates_handle=self._updates_handle)
    try:
        await self._updates_handle
    except asyncio.CancelledError:
        pass

    await self._session.insert_entities(self._entity_cache.get_all_entities())

    session_state, channel_states = self._message_box.session_state()
    for channel_id, pts in channel_states.items():
        await self._session.insert_channel_state(ChannelState(channel_id=channel_id, pts=pts))

    await self._replace_session_state(**session_state)


async def _switch_dc(self: 'TelegramClient', new_dc):
    """
    Permanently switches the current connection to the new data center.
    """
    self._log[__name__].info('Reconnecting to new data center %s', new_dc)

    await self._replace_session_state(dc_id=new_dc)
    await _disconnect(self)
    return await self.connect()

async def _create_exported_sender(self: 'TelegramClient', dc_id):
    """
    Creates a new exported `MTProtoSender` for the given `dc_id` and
    returns it. This method should be used by `_borrow_exported_sender`.
    """
    # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
    # for clearly showing how to export the authorization
    dc = next(dc for dc in await self._session.get_all_dc() if dc.id == dc_id)
    # Can't reuse self._sender._connection as it has its own seqno.
    #
    # If one were to do that, Telegram would reset the connection
    # with no further clues.
    sender = MTProtoSender(loggers=self._log)
    await self._sender.connect(Connection(
        ip=str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
        port=dc.port,
        transport=self._transport.recreate_fresh(),
        loggers=self._log,
        local_addr=self._local_addr,
    ))
    self._log[__name__].info('Exporting auth for new borrowed sender in %s', dc)
    auth = await self(_tl.fn.auth.ExportAuthorization(dc_id))
    req = _tl.fn.InvokeWithLayer(_tl.LAYER, self._init_request(
        query=_tl.fn.auth.ImportAuthorization(id=auth.id, bytes=auth.bytes)
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
        self._log[__name__].debug('Borrowing sender for dc_id %d', dc_id)
        state, sender = self._borrowed_senders.get(dc_id, (None, None))

        if state is None:
            state = _ExportState()
            sender = await _create_exported_sender(self, dc_id)
            sender.dc_id = dc_id
            self._borrowed_senders[dc_id] = (state, sender)

        elif state.need_connect():
            dc = next(dc for dc in await self._session.get_all_dc() if dc.id == dc_id)

            await self._sender.connect(Connection(
                ip=str(ipaddress.ip_address((self._use_ipv6 and dc.ipv6) or dc.ipv4)),
                port=dc.port,
                transport=self._transport.recreate_fresh(),
                loggers=self._log,
                local_addr=self._local_addr,
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
