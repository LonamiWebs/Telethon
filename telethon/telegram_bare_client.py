import logging
import os
import platform
import threading
from datetime import timedelta, datetime
from signal import signal, SIGINT, SIGTERM, SIGABRT
from threading import Lock
from time import sleep
from . import version, utils
from .crypto import rsa
from .errors import (
    RPCError, BrokenAuthKeyError, ServerError, FloodWaitError,
    FloodTestPhoneWaitError, TypeNotFoundError, UnauthorizedError,
    PhoneMigrateError, NetworkMigrateError, UserMigrateError
)
from .network import authenticator, MtProtoSender, Connection, ConnectionMode
from .sessions import Session, SQLiteSession
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
from .tl.functions.updates import GetStateRequest
from .tl.types.auth import ExportedAuthorization
from .update_state import UpdateState

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
                 connection_mode=ConnectionMode.TCP_FULL,
                 use_ipv6=False,
                 proxy=None,
                 update_workers=None,
                 spawn_read_thread=False,
                 timeout=timedelta(seconds=5),
                 loop=None,
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

        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash

        # This is the main sender, which will be used from the thread
        # that calls .connect(). Every other thread will spawn a new
        # temporary connection. The connection on this one is always
        # kept open so Telegram can send us updates.
        self._sender = MtProtoSender(self.session, Connection(
            mode=connection_mode, proxy=proxy, timeout=timeout
        ))

        # Two threads may be calling reconnect() when the connection is lost,
        # we only want one to actually perform the reconnection.
        self._reconnect_lock = Lock()

        # Cache "exported" sessions as 'dc_id: Session' not to recreate
        # them all the time since generating a new key is a relatively
        # expensive operation.
        self._exported_sessions = {}

        # This member will process updates if enabled.
        # One may change self.updates.enabled at any later point.
        self.updates = UpdateState(workers=update_workers)

        # Used on connection - the user may modify these and reconnect
        system = platform.uname()
        self.device_model = device_model or system.system or 'Unknown'
        self.system_version = system_version or system.release or '1.0'
        self.app_version = app_version or self.__version__
        self.lang_code = lang_code
        self.system_lang_code = system_lang_code

        # Despite the state of the real connection, keep track of whether
        # the user has explicitly called .connect() or .disconnect() here.
        # This information is required by the read thread, who will be the
        # one attempting to reconnect on the background *while* the user
        # doesn't explicitly call .disconnect(), thus telling it to stop
        # retrying. The main thread, knowing there is a background thread
        # attempting reconnection as soon as it happens, will just sleep.
        self._user_connected = False

        # Save whether the user is authorized here (a.k.a. logged in)
        self._authorized = None  # None = We don't know yet

        # The first request must be in invokeWithLayer(initConnection(X)).
        # See https://core.telegram.org/api/invoking#saving-client-info.
        self._first_request = True

        # Constantly read for results and updates from within the main client,
        # if the user has left enabled such option.
        self._spawn_read_thread = spawn_read_thread
        self._recv_thread = None
        self._idling = threading.Event()

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

        # Some errors are known but there's nothing we can do from the
        # background thread. If any of these happens, call .disconnect(),
        # and raise them next time .invoke() is tried to be called.
        self._background_error = None

    # endregion

    # region Connecting

    def connect(self, _sync_updates=True):
        """Connects to the Telegram servers, executing authentication if
           required. Note that authenticating to the Telegram servers is
           not the same as authenticating the desired user itself, which
           may require a call (or several) to 'sign_in' for the first time.

           Note that the optional parameters are meant for internal use.

           If '_sync_updates', sync_updates() will be called and a
           second thread will be started if necessary. Note that this
           will FAIL if the client is not connected to the user's
           native data center, raising a "UserMigrateError", and
           calling .disconnect() in the process.
        """
        __log__.info('Connecting to %s:%d...',
                     self.session.server_address, self.session.port)

        self._background_error = None  # Clear previous errors

        try:
            self._sender.connect()
            __log__.info('Connection success!')

            # Connection was successful! Try syncing the update state
            # UNLESS '_sync_updates' is False (we probably are in
            # another data center and this would raise UserMigrateError)
            # to also assert whether the user is logged in or not.
            self._user_connected = True
            if self._authorized is None and _sync_updates:
                try:
                    self.sync_updates()
                    self._set_connected_and_authorized()
                except UnauthorizedError:
                    self._authorized = False
            elif self._authorized:
                self._set_connected_and_authorized()

            return True

        except TypeNotFoundError as e:
            # This is fine, probably layer migration
            __log__.warning('Connection failed, got unexpected type with ID '
                            '%s. Migrating?', hex(e.invalid_constructor_id))
            self.disconnect()
            return self.connect(_sync_updates=_sync_updates)

        except (RPCError, ConnectionError) as e:
            # Probably errors from the previous session, ignore them
            __log__.error('Connection failed due to %s', e)
            self.disconnect()
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

    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        __log__.info('Disconnecting...')
        self._user_connected = False  # This will stop recv_thread's loop

        __log__.debug('Stopping all workers...')
        self.updates.stop_workers()

        # This will trigger a "ConnectionResetError" on the recv_thread,
        # which won't attempt reconnecting as ._user_connected is False.
        __log__.debug('Disconnecting the socket...')
        self._sender.disconnect()

        # TODO Shall we clear the _exported_sessions, or may be reused?
        self._first_request = True  # On reconnect it will be first again
        self.session.close()

    def _reconnect(self, new_dc=None):
        """If 'new_dc' is not set, only a call to .connect() will be made
           since it's assumed that the connection has been lost and the
           library is reconnecting.

           If 'new_dc' is set, the client is first disconnected from the
           current data center, clears the auth key for the old DC, and
           connects to the new data center.
        """
        if new_dc is None:
            if self.is_connected():
                __log__.info('Reconnection aborted: already connected')
                return True

            try:
                __log__.info('Attempting reconnection...')
                return self.connect()
            except ConnectionResetError as e:
                __log__.warning('Reconnection failed due to %s', e)
                return False
        else:
            # Since we're reconnecting possibly due to a UserMigrateError,
            # we need to first know the Data Centers we can connect to. Do
            # that before disconnecting.
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
        self._sender.connection.conn.proxy = proxy

    # endregion

    # region Working with different connections/Data Centers

    def _on_read_thread(self):
        return self._recv_thread is not None and \
               threading.get_ident() == self._recv_thread.ident

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

    def __call__(self, *requests, retries=5):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           The invoke will be retried up to 'retries' times before raising
           RuntimeError().
        """
        if not all(isinstance(x, TLObject) and
                   x.content_related for x in requests):
            raise TypeError('You can only invoke requests, not types!')

        if self._background_error:
            raise self._background_error

        for request in requests:
            request.resolve(self, utils)

        # For logging purposes
        if len(requests) == 1:
            which = type(requests[0]).__name__
        else:
            which = '{} requests ({})'.format(
                len(requests), [type(x).__name__ for x in requests])

        # Determine the sender to be used (main or a new connection)
        __log__.debug('Invoking %s', which)
        call_receive = \
            not self._idling.is_set() or self._reconnect_lock.locked()

        for retry in range(retries):
            result = self._invoke(call_receive, *requests)
            if result is not None:
                return result

            __log__.warning('Invoking %s failed %d times, '
                            'reconnecting and retrying',
                            [str(x) for x in requests], retry + 1)
            sleep(1)
            # The ReadThread has priority when attempting reconnection,
            # since this thread is constantly running while __call__ is
            # only done sometimes. Here try connecting only once/retry.
            if not self._reconnect_lock.locked():
                with self._reconnect_lock:
                    self._reconnect()

        raise RuntimeError('Number of retries reached 0 for {}.'.format(
            [type(x).__name__ for x in requests]
        ))

    # Let people use client.invoke(SomeRequest()) instead client(...)
    invoke = __call__

    def _invoke(self, call_receive, *requests):
        try:
            # Ensure that we start with no previous errors (i.e. resending)
            for x in requests:
                x.confirm_received.clear()
                x.rpc_error = None

            if not self.session.auth_key:
                __log__.info('Need to generate new auth key before invoking')
                self._first_request = True
                self.session.auth_key, self.session.time_offset = \
                    authenticator.do_authentication(self._sender.connection)

            if self._first_request:
                __log__.info('Initializing a new connection while invoking')
                if len(requests) == 1:
                    requests = [self._wrap_init_connection(requests[0])]
                else:
                    # We need a SINGLE request (like GetConfig) to init conn.
                    # Once that's done, the N original requests will be
                    # invoked.
                    TelegramBareClient._config = self(
                        self._wrap_init_connection(GetConfigRequest())
                    )

            self._sender.send(*requests)

            if not call_receive:
                # TODO This will be slightly troublesome if we allow
                # switching between constant read or not on the fly.
                # Must also watch out for calling .read() from two places,
                # in which case a Lock would be required for .receive().
                for x in requests:
                    x.confirm_received.wait(
                        self._sender.connection.get_timeout()
                    )
            else:
                while not all(x.confirm_received.is_set() for x in requests):
                    self._sender.receive(update_state=self.updates)

        except BrokenAuthKeyError:
            __log__.error('Authorization key seems broken and was invalid!')
            self.session.auth_key = None

        except TypeNotFoundError as e:
            # Only occurs when we call receive. May happen when
            # we need to reconnect to another DC on login and
            # Telegram somehow sends old objects (like configOld)
            self._first_request = True
            __log__.warning('Read unknown TLObject code ({}). '
                            'Setting again first_request flag.'
                            .format(hex(e.invalid_constructor_id)))

        except TimeoutError:
            __log__.warning('Invoking timed out')  # We will just retry

        except ConnectionResetError as e:
            __log__.warning('Connection was reset while invoking')
            if self._user_connected:
                # Server disconnected us, __call__ will try reconnecting.
                return None
            else:
                # User never called .connect(), so raise this error.
                raise RuntimeError('Tried to invoke without .connect()') from e

        # Clear the flag if we got this far
        self._first_request = False

        try:
            raise next(x.rpc_error for x in requests if x.rpc_error)
        except StopIteration:
            if any(x.result is None for x in requests):
                # "A container may only be accepted or
                # rejected by the other party as a whole."
                return None

            if len(requests) == 1:
                return requests[0].result
            else:
                return [x.result for x in requests]

        except (PhoneMigrateError, NetworkMigrateError,
                UserMigrateError) as e:

            # TODO What happens with the background thread here?
            # For normal use cases, this won't happen, because this will only
            # be on the very first connection (not authorized, not running),
            # but may be an issue for people who actually travel?
            self._reconnect(new_dc=e.new_dc)
            return self._invoke(call_receive, *requests)

        except ServerError as e:
            # Telegram is having some issues, just retry
            __log__.error('Telegram servers are having internal errors %s', e)

        except (FloodWaitError, FloodTestPhoneWaitError) as e:
            __log__.warning('Request invoked too often, wait %ds', e.seconds)
            if e.seconds > self.session.flood_sleep_threshold | 0:
                raise

            sleep(e.seconds)

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

    def sync_updates(self):
        """Synchronizes self.updates to their initial state. Will be
           called automatically on connection if self.updates.enabled = True,
           otherwise it should be called manually after enabling updates.
        """
        self.updates.process(self(GetStateRequest()))
        self._last_state = datetime.now()

    # endregion

    # region Constant read

    def _set_connected_and_authorized(self):
        self._authorized = True
        self.updates.setup_workers()
        if self._spawn_read_thread and self._recv_thread is None:
            self._recv_thread = threading.Thread(
                name='ReadThread', daemon=True,
                target=self._recv_thread_impl
            )
            self._recv_thread.start()

    def _signal_handler(self, signum, frame):
        if self._user_connected:
            self.disconnect()
        else:
            os._exit(1)

    def idle(self, stop_signals=(SIGINT, SIGTERM, SIGABRT)):
        """
        Idles the program by looping forever and listening for updates
        until one of the signals are received, which breaks the loop.

        :param stop_signals:
            Iterable containing signals from the signal module that will
            be subscribed to TelegramClient.disconnect() (effectively
            stopping the idle loop), which will be called on receiving one
            of those signals.
        :return:
        """
        if self._spawn_read_thread and not self._on_read_thread():
            raise RuntimeError('Can only idle if spawn_read_thread=False')

        self._idling.set()
        for sig in stop_signals:
            signal(sig, self._signal_handler)

        if self._on_read_thread():
            __log__.info('Starting to wait for items from the network')
        else:
            __log__.info('Idling to receive items from the network')

        while self._user_connected:
            try:
                if datetime.now() > self._last_ping + self._ping_delay:
                    self._sender.send(PingRequest(
                        int.from_bytes(os.urandom(8), 'big', signed=True)
                    ))
                    self._last_ping = datetime.now()

                if datetime.now() > self._last_state + self._state_delay:
                    self._sender.send(GetStateRequest())
                    self._last_state = datetime.now()

                __log__.debug('Receiving items from the network...')
                self._sender.receive(update_state=self.updates)
            except TimeoutError:
                # No problem
                __log__.debug('Receiving items from the network timed out')
            except ConnectionResetError:
                if self._user_connected:
                    __log__.error('Connection was reset while receiving '
                                  'items. Reconnecting')
                with self._reconnect_lock:
                    while self._user_connected and not self._reconnect():
                        sleep(0.1)  # Retry forever, this is instant messaging

                if self.is_connected():
                    # Telegram seems to kick us every 1024 items received
                    # from the network not considering things like bad salt.
                    # We must execute some *high level* request (that's not
                    # a ping) if we want to receive updates again.
                    # TODO Test if getDifference works too (better alternative)
                    self._sender.send(GetStateRequest())
            except:
                self._idling.clear()
                raise

        self._idling.clear()
        __log__.info('Connection closed by the user, not reading anymore')

    # By using this approach, another thread will be
    # created and started upon connection to constantly read
    # from the other end. Otherwise, manual calls to .receive()
    # must be performed. The MtProtoSender cannot be connected,
    # or an error will be thrown.
    #
    # This way, sending and receiving will be completely independent.
    def _recv_thread_impl(self):
        # This thread is "idle" (only listening for updates), but also
        # excepts everything unlike the manual idle because it should
        # not crash.
        while self._user_connected:
            try:
                self.idle(stop_signals=tuple())
            except Exception as error:
                __log__.exception('Unknown exception in the read thread! '
                                  'Disconnecting and leaving it to main thread')
                # Unknown exception, pass it to the main thread

                try:
                    import socks
                    if isinstance(error, (
                            socks.GeneralProxyError, socks.ProxyConnectionError
                    )):
                        # This is a known error, and it's not related to
                        # Telegram but rather to the proxy. Disconnect and
                        # hand it over to the main thread.
                        self._background_error = error
                        self.disconnect()
                        break
                except ImportError:
                    "Not using PySocks, so it can't be a proxy error"

        self._recv_thread = None

    # endregion
