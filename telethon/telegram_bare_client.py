import asyncio
import logging
import os
from asyncio import Lock, Event
from datetime import timedelta, datetime
import platform
from . import version, utils
from .crypto import rsa
from .errors import (
    RPCError, BrokenAuthKeyError, ServerError, FloodWaitError,
    FloodTestPhoneWaitError, TypeNotFoundError, UnauthorizedError,
    PhoneMigrateError, NetworkMigrateError, UserMigrateError, AuthKeyError,
    RpcCallFailError
)
from .network import authenticator, MtProtoSender, ConnectionTcpFull
from .sessions import Session
from .tl import TLObject
from .tl.all_tlobjects import LAYER
from .tl.functions import (
    InitConnectionRequest, InvokeWithLayerRequest, PingRequest
)
from .tl.functions.auth import (
    ImportAuthorizationRequest, ExportAuthorizationRequest
)
from .tl.functions.help import (
    GetCdnConfigRequest, GetConfigRequest
)
from .tl.functions.updates import GetStateRequest, GetDifferenceRequest
from .tl.types import (
    Pong, PeerUser, PeerChat, Message, Updates, UpdateShort, UpdateNewChannelMessage, UpdateEditChannelMessage,
    UpdateDeleteChannelMessages, UpdateChannelTooLong, UpdateNewMessage, NewSessionCreated, UpdatesTooLong,
    UpdateShortSentMessage, MessageEmpty, UpdateShortMessage, UpdateShortChatMessage, UpdatesCombined
)
from .tl.types.auth import ExportedAuthorization
from .tl.types.messages import AffectedMessages, AffectedHistory
from .tl.types.updates import DifferenceEmpty, DifferenceTooLong, DifferenceSlice

MAX_TIMEOUT = 15  # in seconds
DEFAULT_DC_ID = 4
DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '[2001:67c:4e8:f002::a]'
DEFAULT_PORT = 443

__log__ = logging.getLogger(__name__)


class TelegramBareClient:
    """Bare Telegram Client with just the minimum -

       The reason to distinguish between a MtProtoSender and a
       TelegramClient itself is because the sender is just that,
       a sender, which should know nothing about Telegram but
       rather how to handle this specific connection.

       The TelegramClient itself should know how to initialize
       a proper connection to the servers, as well as other basic
       methods such as disconnection and reconnection.

       This distinction between a bare client and a full client
       makes it possible to create clones of the bare version
       (by using the same session, IP address and port) to be
       able to execute queries on either, without the additional
       cost that would involve having the methods for signing in,
       logging out, and such.
    """

    # Current TelegramClient version
    __version__ = version.__version__

    # TODO Make this thread-safe, all connections share the same DC
    _config = None  # Server configuration (with .dc_options)

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 *,
                 connection=ConnectionTcpFull,
                 use_ipv6=False,
                 proxy=None,
                 timeout=timedelta(seconds=5),
                 ping_delay=timedelta(minutes=1),
                 update_handler=None,
                 unauthorized_handler=None,
                 loop=None,
                 report_errors=None,
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
        if not isinstance(session, Session):
            raise TypeError('The given session must be a Session instance.')

        self._loop = loop if loop else asyncio.get_event_loop()

        # ':' in session.server_address is True if it's an IPv6 address
        if (not session.server_address or
                (':' in session.server_address) != use_ipv6):
            session.set_dc(
                DEFAULT_DC_ID,
                DEFAULT_IPV6_IP if self._use_ipv6 else DEFAULT_IPV4_IP,
                DEFAULT_PORT
            )

        if report_errors is not None:
            session.report_errors = report_errors
        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash

        # This is the main sender, which will be used from the thread
        # that calls .connect(). Every other thread will spawn a new
        # temporary connection. The connection on this one is always
        # kept open so Telegram can send us updates.
        if isinstance(connection, type):
            connection = connection(proxy=proxy, timeout=timeout, loop=self._loop)

        self._sender = MtProtoSender(self.session, connection)

        # Two co-routines may be calling reconnect() when the connection
        # is lost, we only want one to actually perform the reconnection.
        self._reconnect_lock = Lock(loop=self._loop)

        # Cache "exported" sessions as 'dc_id: Session' not to recreate
        # them all the time since generating a new key is a relatively
        # expensive operation.
        self._exported_sessions = {}

        # Used on connection - the user may modify these and reconnect
        system = platform.uname()
        self.device_model = device_model or system.system or 'Unknown'
        self.system_version = system_version or system.release or '1.0'
        self.app_version = app_version or self.__version__
        self.lang_code = lang_code
        self.system_lang_code = system_lang_code

        self._state = None
        self._sync_loading = False
        self.update_handler = update_handler
        self.unauthorized_handler = unauthorized_handler
        self._last_update = datetime.now()

        # Despite the state of the real connection, keep track of whether
        # the user has explicitly called .connect() or .disconnect() here.
        # This information is required by the read thread, who will be the
        # one attempting to reconnect on the background *while* the user
        # doesn't explicitly call .disconnect(), thus telling it to stop
        # retrying. The main thread, knowing there is a background thread
        # attempting reconnection as soon as it happens, will just sleep.
        self._user_connected = Event(loop=self._loop)
        self._authorized = False
        self._shutdown = False
        self._recv_loop = None
        self._ping_loop = None
        self._reconnection_loop = None

        if isinstance(ping_delay, timedelta):
            self._ping_delay = ping_delay.seconds
        elif isinstance(ping_delay, (int, float)):
            self._ping_delay = float(ping_delay)
        else:
            raise TypeError('Invalid timeout type', type(timeout))

    def __del__(self):
        self.disconnect()

    async def connect(self):
        try:
            if not self._sender.is_connected():
                await self._sender.connect()
            if not self.session.auth_key:
                try:
                    self.session.auth_key, self.session.time_offset = \
                        await authenticator.do_authentication(self._sender.connection)
                    await self.session.save()
                except BrokenAuthKeyError:
                    self._user_connected.clear()
                    return False

            if TelegramBareClient._config is None:
                TelegramBareClient._config = await self(self._wrap_init_connection(GetConfigRequest()))

            if not self._authorized:
                try:
                    self._state = await self(self._wrap_init_connection(GetStateRequest()))
                    self._authorized = True
                except UnauthorizedError:
                    self._authorized = False

            self.run_loops()
            self._user_connected.set()
            return True

        except TypeNotFoundError as e:
            # This is fine, probably layer migration
            __log__.warning('Connection failed, got unexpected type with ID '
                            '%s. Migrating?', hex(e.invalid_constructor_id))
            self.disconnect(False)
            return await self.connect()

        except AuthKeyError as e:
            # As of late March 2018 there were two AUTH_KEY_DUPLICATED
            # reports. Retrying with a clean auth_key should fix this.
            if not self._authorized:
                __log__.warning('Auth key error %s. Clearing it and retrying.', e)
                self.disconnect(False)
                self.session.auth_key = None
                return self.connect()
            else:
                raise

        except (RPCError, ConnectionError) as e:
            # Probably errors from the previous session, ignore them
            __log__.error('Connection failed due to %s', e)
            self.disconnect(False)
            return False

    def is_connected(self):
        return self._sender.is_connected()

    def _wrap_init_connection(self, query):
        """Wraps query around InvokeWithLayerRequest(InitConnectionRequest())"""
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

    def disconnect(self, shutdown=True):
        """Disconnects from the Telegram server"""
        self._shutdown = shutdown
        self._user_connected.clear()
        self._sender.disconnect(clear_pendings=shutdown)

    async def _reconnect(self, new_dc=None):
        """If 'new_dc' is not set, only a call to .connect() will be made
           since it's assumed that the connection has been lost and the
           library is reconnecting.

           If 'new_dc' is set, the client is first disconnected from the
           current data center, clears the auth key for the old DC, and
           connects to the new data center.
        """
        await self._reconnect_lock.acquire()
        try:
            # Another thread may have connected again, so check that first
            if self.is_connected() and new_dc is None:
                return True

            if new_dc is not None:
                dc = await self._get_dc(new_dc)
                self.disconnect(False)
                self.session.set_dc(dc.id, dc.ip_address, dc.port)
                await self.session.save()

            return await self.connect()
        except (ConnectionResetError, TimeoutError):
            return False
        finally:
            self._reconnect_lock.release()

    def set_proxy(self, proxy):
        """Change the proxy used by the connections.
        """
        if self.is_connected():
            raise RuntimeError("You can't change the proxy while connected.")
        self._sender.connection.conn.proxy = proxy

    # endregion

    # region Working with different connections/Data Centers

    async def _get_dc(self, dc_id, cdn=False):
        """Gets the Data Center (DC) associated to 'dc_id'"""
        if not TelegramBareClient._config:
            TelegramBareClient._config = await self(GetConfigRequest())

        try:
            if cdn:
                # Ensure we have the latest keys for the CDNs
                for pk in await (self(GetCdnConfigRequest())).public_keys:
                    rsa.add_key(pk.public_key)

            return next(
                dc for dc in TelegramBareClient._config.dc_options
                if dc.id == dc_id and bool(dc.ipv6) == self._use_ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            if not cdn:
                raise

            # New configuration, perhaps a new CDN was added?
            TelegramBareClient._config = await self(GetConfigRequest())
            return await self._get_dc(dc_id, cdn=cdn)

    async def _get_exported_client(self, dc_id):
        """Creates and connects a new TelegramBareClient for the desired DC.

           If it's the first time calling the method with a given dc_id,
           a new session will be first created, and its auth key generated.
           Exporting/Importing the authorization will also be done so that
           the auth is bound with the key.
        """
        # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
        # for clearly showing how to export the authorization! ^^
        session = self._exported_sessions.get(dc_id, None)
        if session:
            export_auth = None  # Already bound with the auth key
        else:
            # TODO Add a lock, don't allow two threads to create an auth key
            # (when calling .connect() if there wasn't a previous session).
            # for the same data center.
            dc = await self._get_dc(dc_id)

            # Export the current authorization to the new DC.
            __log__.info('Exporting authorization for data center %s', dc)
            export_auth = await self(ExportAuthorizationRequest(dc_id))

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
            timeout=self._sender.connection.get_timeout(),
            loop=self._loop
        )
        await client.connect()
        if isinstance(export_auth, ExportedAuthorization):
            await client(ImportAuthorizationRequest(
                id=export_auth.id, bytes=export_auth.bytes
            ))
        elif export_auth is not None:
            __log__.warning('Unknown export auth type %s', export_auth)

        return client

    async def _get_cdn_client(self, cdn_redirect):
        """Similar to ._get_exported_client, but for CDNs"""
        session = self._exported_sessions.get(cdn_redirect.dc_id, None)
        if not session:
            dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = self.session.clone()
            session.set_dc(dc.id, dc.ip_address, dc.port)
            self._exported_sessions[cdn_redirect.dc_id] = session

        __log__.info('Creating new CDN client')
        client = TelegramBareClient(
            session, self.api_id, self.api_hash,
            proxy=self._sender.connection.conn.proxy,
            timeout=self._sender.connection.get_timeout(),
            loop=self._loop
        )

        # This will make use of the new RSA keys for this specific CDN.
        #
        # We won't be calling GetConfigRequest because it's only called
        # when needed by ._get_dc, and also it's static so it's likely
        # set already. Avoid invoking non-CDN methods by not syncing updates.
        await client.connect()
        return client

    # endregion

    # region Invoking Telegram requests

    async def __call__(self, request, retries=5, ordered=False):
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
        single = not utils.is_list_like(request)
        if single:
            request = (request,)

        if not all(isinstance(x, TLObject) and
                   x.content_related for x in request):
            raise TypeError('You can only invoke requests, not types!')

        for r in request:
            await r.resolve(self, utils)

        # For logging purposes
        if single:
            which = type(request[0]).__name__
        else:
            which = '{} requests ({})'.format(
                len(request), [type(x).__name__ for x in request])

        is_ping = any(isinstance(x, PingRequest) for x in request)
        msg_ids = []

        __log__.debug('Invoking %s', which)
        try:
            for retry in range(retries):
                result = None
                for sub_retry in range(retries):
                    msg_ids, result = await self._invoke(retry, request, ordered, msg_ids)
                    if msg_ids:
                        break
                    if not self.is_connected():
                        break
                    __log__.error('Subretry %d is failed' % sub_retry)
                if result is None:
                    if not is_ping:
                        try:
                            pong = await self(PingRequest(int.from_bytes(os.urandom(8), 'big', signed=True)), retries=1)
                            if isinstance(pong, Pong):
                                __log__.error('Connection is live, but no answer on %d retry' % retry)
                                continue
                        except RuntimeError:
                            pass  # continue to reconnect
                    if self.is_connected() and (retry + 1) % 2 == 0:
                        __log__.error('Force disconnect on %d retry' % retry)
                        self.disconnect(False)
                        self._sender.forget_pendings(msg_ids)
                        msg_ids = []
                    if not self.is_connected():
                        __log__.error('Pause before new retry on %d retry' % retry)
                        await asyncio.sleep(retry + 1, loop=self._loop)
                else:
                    return result[0] if single else result
        finally:
            self._sender.forget_pendings(msg_ids)

        raise RuntimeError('Number of retries is exceeded for {}.'.format(which))

    # Let people use client.invoke(SomeRequest()) instead client(...)
    invoke = __call__

    async def _invoke(self, retry, requests, ordered, msg_ids):
        try:
            if not msg_ids:
                msg_ids = await self._sender.send(requests, ordered)

                # Ensure that we start with no previous errors (i.e. resending)
                for x in requests:
                    x.rpc_error = None

            if self._user_connected.is_set():
                fut = asyncio.gather(*list(map(lambda x: x.confirm_received.wait(), requests)), loop=self._loop)
                self._loop.call_later(self._sender.connection.get_timeout(), fut.cancel)
                await fut
            else:
                while not all(x.confirm_received.is_set() for x in requests):
                    await self._sender.receive(self._updates_handler)
        except (TimeoutError, asyncio.CancelledError):
            __log__.error('Timeout on %d retry' % retry)

        except ConnectionResetError as e:
            if self._shutdown:
                raise
            __log__.error('Connection reset on %d retry: %r' % (retry, e))

        try:
            raise next(x.rpc_error for x in requests if x.rpc_error)
        except StopIteration:
            if any(x.result is None for x in requests):
                # "A container may only be accepted or
                # rejected by the other party as a whole."
                return msg_ids, None

            for req in requests:
                if isinstance(req.result, TLObject) and req.result.SUBCLASS_OF_ID == Updates.SUBCLASS_OF_ID:
                    self._updates_handler(req.result, False, False)
                if isinstance(req.result, (AffectedMessages, AffectedHistory)):  # due to affect to pts
                    self._updates_handler(UpdateShort(req.result, None), False, False)

            return msg_ids, [x.result for x in requests]

        except (PhoneMigrateError, NetworkMigrateError, UserMigrateError) as e:
            if isinstance(e, (PhoneMigrateError, NetworkMigrateError)):
                if self._authorized:
                    raise
                else:
                    self.session.auth_key = None  # Force creating new auth_key

            __log__.error(
                'DC error when invoking request, '
                'attempting to reconnect at DC {}'.format(e.new_dc)
            )

            await self._reconnect(new_dc=e.new_dc)
            self._sender.forget_pendings(msg_ids)
            msg_ids = []
            return msg_ids, None

        except (ServerError, RpcCallFailError) as e:
            # Telegram is having some issues, just retry
            __log__.warning('Telegram is having internal issues: %s', e)

        except (FloodWaitError, FloodTestPhoneWaitError) as e:
            __log__.warning('Request invoked too often, wait %ds', e.seconds)
            if e.seconds > self.session.flood_sleep_threshold | 0:
                raise

            await asyncio.sleep(e.seconds, loop=self._loop)
            return msg_ids, None

        except UnauthorizedError:
            if self._authorized:
                __log__.error('Authorization has lost')
                self._authorized = False
                self.disconnect()
                if self.unauthorized_handler:
                    await self.unauthorized_handler(self)
            raise

    # Some really basic functionality

    def is_user_authorized(self):
        """Has the user been authorized yet
           (code request sent and confirmed)?"""
        return self._authorized

    def get_input_entity(self, peer):
        """
        Stub method, no functionality so that calling
        ``.get_input_entity()`` from ``.resolve()`` doesn't fail.
        """
        return peer

    # endregion

    # region Updates handling

    async def _handle_update(self, update, seq_start, seq, date, do_get_diff, do_handlers, users=(), chats=()):
        if isinstance(update, (UpdateNewChannelMessage, UpdateEditChannelMessage,
                               UpdateDeleteChannelMessages, UpdateChannelTooLong)):
            # TODO: channel updates have their own pts sequences, so requires individual pts'es
            return  # ignore channel updates to keep pts in the main _state in the correct state
        if hasattr(update, 'pts'):
            new_pts = self._state.pts + getattr(update, 'pts_count', 0)
            if new_pts < update.pts:
                __log__.debug('Have got a hole between pts => waiting 0.5 sec')
                await asyncio.sleep(0.5, loop=self._loop)
            if new_pts < update.pts:
                if do_get_diff and not self._sync_loading:
                    __log__.debug('The hole between pts has not disappeared => going to get differences')
                    self._sync_loading = True
                    asyncio.ensure_future(self._get_difference(), loop=self._loop)
                return
            if update.pts > self._state.pts:
                self._state.pts = update.pts
            elif getattr(update, 'pts_count', 0) > 0:
                __log__.debug('Have got the duplicate update (basing on pts) => ignoring')
                return
        elif hasattr(update, 'qts'):
            if self._state.qts + 1 < update.qts:
                __log__.debug('Have got a hole between qts => waiting 0.5 sec')
                await asyncio.sleep(0.5, loop=self._loop)
            if self._state.qts + 1 < update.qts:
                if do_get_diff and not self._sync_loading:
                    __log__.debug('The hole between qts has not disappeared => going to get differences')
                    self._sync_loading = True
                    asyncio.ensure_future(self._get_difference(), loop=self._loop)
                return
            if update.qts > self._state.qts:
                self._state.qts = update.qts
            else:
                __log__.debug('Have got the duplicate update (basing on qts) => ignoring')
                return
        elif seq > 0:
            if seq_start > self._state.seq + 1:
                __log__.debug('Have got a hole between seq => waiting 0.5 sec')
                await asyncio.sleep(0.5, loop=self._loop)
            if seq_start > self._state.seq + 1:
                if do_get_diff and not self._sync_loading:
                    __log__.debug('The hole between seq has not disappeared => going to get differences')
                    self._sync_loading = True
                    asyncio.ensure_future(self._get_difference(), loop=self._loop)
                return
            self._state.seq = seq
            self._state.date = max(self._state.date, date)

        if do_handlers and self.update_handler:
            asyncio.ensure_future(self.update_handler(self, update, users, chats), loop=self._loop)

    async def _get_difference(self):
        self._sync_loading = True
        try:
            difference = await self(GetDifferenceRequest(self._state.pts, self._state.date, self._state.qts))
            if isinstance(difference, DifferenceEmpty):
                __log__.debug('Have got DifferenceEmpty => just update seq and date')
                self._state.seq = difference.seq
                self._state.date = difference.date
                return
            if isinstance(difference, DifferenceTooLong):
                __log__.debug('Have got DifferenceTooLong => update pts and try again')
                self._state.pts = difference.pts
                asyncio.ensure_future(self._get_difference(), loop=self._loop)
                return
            __log__.debug('Preparing updates from differences')
            self._state = difference.intermediate_state \
                if isinstance(difference, DifferenceSlice) else difference.state
            messages = [UpdateNewMessage(msg, self._state.pts, 0) for msg in difference.new_messages]
            self._updates_handler(
                Updates(messages + difference.other_updates,
                        difference.users, difference.chats, self._state.date, self._state.seq),
                False
            )
            if isinstance(difference, DifferenceSlice):
                asyncio.ensure_future(self._get_difference(), loop=self._loop)
        except ConnectionResetError:  # it happens on unauth due to _get_difference is often on the background
            pass
        except Exception as e:
            __log__.exception('Exception on _get_difference: %r', e)
        finally:
            self._sync_loading = False

    # TODO: Some of logic was moved from MtProtoSender and probably must be moved back.
    def _updates_handler(self, updates, do_get_diff=True, do_handlers=True):
        if do_get_diff:
            self._last_update = datetime.now()
        if isinstance(updates, NewSessionCreated):
            self.session.salt = updates.server_salt
        if self._state is None:
            return False  # not ready yet
        if self._sync_loading and do_get_diff:
            return False  # ignore all if in sync except from difference (do_get_diff = False)
        if isinstance(updates, (NewSessionCreated, UpdatesTooLong)):
            if do_get_diff:  # to prevent possible loops
                __log__.debug('Have got %s => going to get differences', type(updates))
                self._sync_loading = True
                asyncio.ensure_future(self._get_difference(), loop=self._loop)
            return False

        seq = getattr(updates, 'seq', 0)
        seq_start = getattr(updates, 'seq_start', seq)
        date = getattr(updates, 'date', self._state.date)

        if isinstance(updates, UpdateShort):
            asyncio.ensure_future(
                self._handle_update(updates.update, seq_start, seq, date, do_get_diff, do_handlers),
                loop=self._loop
            )
            return True

        if isinstance(updates, UpdateShortSentMessage):
            asyncio.ensure_future(self._handle_update(
                UpdateNewMessage(MessageEmpty(updates.id), updates.pts, updates.pts_count),
                seq_start, seq, date, do_get_diff, do_handlers
            ), loop=self._loop)
            return True

        if isinstance(updates, (UpdateShortMessage, UpdateShortChatMessage)):
            from_id = getattr(updates, 'from_id', self.session.user_id)
            to_id = updates.user_id if isinstance(updates, UpdateShortMessage) else updates.chat_id
            if not updates.out:
                from_id, to_id = to_id, from_id
            to_id = PeerUser(to_id) if isinstance(updates, UpdateShortMessage) else PeerChat(to_id)
            message = Message(
                id=updates.id, to_id=to_id, date=updates.date, message=updates.message, out=updates.out,
                mentioned=updates.mentioned, media_unread=updates.media_unread, silent=updates.silent,
                from_id=from_id, fwd_from=updates.fwd_from, via_bot_id=updates.via_bot_id,
                reply_to_msg_id=updates.reply_to_msg_id, entities=updates.entities
            )
            asyncio.ensure_future(self._handle_update(
                UpdateNewMessage(message, updates.pts, updates.pts_count),
                seq_start, seq, date, do_get_diff, do_handlers
            ), loop=self._loop)
            return True

        if isinstance(updates, (Updates, UpdatesCombined)):
            for upd in updates.updates:
                asyncio.ensure_future(
                    self._handle_update(upd, seq_start, seq, date, do_get_diff, do_handlers,
                                        updates.users, updates.chats),
                    loop=self._loop
                )
            return True

        if do_get_diff:  # to prevent possible loops
            __log__.debug('Have got unsupported type of updates: %s => going to get differences', type(updates))
            self._sync_loading = True
            asyncio.ensure_future(self._get_difference(), loop=self._loop)

        return False

    def run_loops(self):
        if self._recv_loop is None:
            self._recv_loop = asyncio.ensure_future(self._recv_loop_impl(), loop=self._loop)
        if self._ping_loop is None:
            self._ping_loop = asyncio.ensure_future(self._ping_loop_impl(), loop=self._loop)

    async def _ping_loop_impl(self):
        while True:
            if self._shutdown:
                break
            try:
                await self._user_connected.wait()
                await self(PingRequest(int.from_bytes(os.urandom(8), 'big', signed=True)))
                await asyncio.sleep(self._ping_delay, loop=self._loop)
            except RuntimeError:
                pass  # Can be not happy due to connection problems
            except asyncio.CancelledError:
                break
            except:
                self._ping_loop = None
                raise
        self._ping_loop = None

    async def _recv_loop_impl(self):
        timeout = 1
        while True:
            if self._shutdown:
                break
            try:
                if self._user_connected.is_set():
                    if self._authorized and datetime.now() - self._last_update > timedelta(minutes=15):
                        __log__.debug('No updates for 15 minutes => going to get differences')
                        self._last_update = datetime.now()
                        self._sync_loading = True
                        asyncio.ensure_future(self._get_difference(), loop=self._loop)
                    await self._sender.receive(self._updates_handler)
                else:
                    if await self._reconnect():
                        __log__.info('Connection has established')
                        timeout = 1
                    else:
                        await asyncio.sleep(timeout, loop=self._loop)
                        timeout = min(timeout * 2, MAX_TIMEOUT)
            except TimeoutError:
                # No problem.
                pass
            except ConnectionResetError as error:
                __log__.info('Connection reset error in recv loop: %r' % error)
                self._user_connected.clear()
            except asyncio.CancelledError:
                self.disconnect()
                break
            except Exception as error:
                # Unknown exception, pass it to the main thread
                __log__.exception('[ERROR: %r] on the read loop, please report', error)
        self._recv_loop = None
        if self._shutdown and self._ping_loop:
            self._ping_loop.cancel()

    # endregion
