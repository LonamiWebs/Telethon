import logging
import os
import threading
import warnings
from datetime import timedelta, datetime
from hashlib import md5
from io import BytesIO
from signal import signal, SIGINT, SIGTERM, SIGABRT
from threading import Lock
from time import sleep

from . import helpers as utils, version
from .crypto import rsa, CdnDecrypter
from .errors import (
    RPCError, BrokenAuthKeyError, ServerError,
    FloodWaitError, FileMigrateError, TypeNotFoundError,
    UnauthorizedError, PhoneMigrateError, NetworkMigrateError, UserMigrateError
)
from .network import authenticator, MtProtoSender, Connection, ConnectionMode
from .tl import TLObject, Session
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
from .tl.functions.upload import (
    GetFileRequest, SaveBigFilePartRequest, SaveFilePartRequest
)
from .tl.types import InputFile, InputFileBig
from .tl.types.auth import ExportedAuthorization
from .tl.types.upload import FileCdnRedirect
from .update_state import UpdateState
from .utils import get_appropriated_part_size


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
                 proxy=None,
                 update_workers=None,
                 spawn_read_thread=False,
                 timeout=timedelta(seconds=5),
                 **kwargs):
        """Refer to TelegramClient.__init__ for docs on this method"""
        if not api_id or not api_hash:
            raise PermissionError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to Telethon's README.rst for more information.")

        # Determine what session object we have
        if isinstance(session, str) or session is None:
            session = Session.try_load_or_create_new(session)
        elif not isinstance(session, Session):
            raise ValueError(
                'The given session must be a str or a Session instance.'
            )

        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash
        if self.api_id < 20:  # official apps must use obfuscated
            connection_mode = ConnectionMode.TCP_OBFUSCATED

        # This is the main sender, which will be used from the thread
        # that calls .connect(). Every other thread will spawn a new
        # temporary connection. The connection on this one is always
        # kept open so Telegram can send us updates.
        self._sender = MtProtoSender(self.session, Connection(
            mode=connection_mode, proxy=proxy, timeout=timeout
        ))

        self._logger = logging.getLogger(__name__)

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
        kwargs['app_version'] = kwargs.get('app_version', self.__version__)
        for name, value in kwargs.items():
            if not hasattr(self.session, name):
                raise ValueError('Unknown named parameter', name)
            setattr(self.session, name, value)

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

        # Uploaded files cache so subsequent calls are instant
        self._upload_cache = {}

        # Constantly read for results and updates from within the main client,
        # if the user has left enabled such option.
        self._spawn_read_thread = spawn_read_thread
        self._recv_thread = None

        # Identifier of the main thread (the one that called .connect()).
        # This will be used to create new connections from any other thread,
        # so that requests can be sent in parallel.
        self._main_thread_ident = None

        # Default PingRequest delay
        self._last_ping = datetime.now()
        self._ping_delay = timedelta(minutes=1)

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
        self._main_thread_ident = threading.get_ident()
        self._background_error = None  # Clear previous errors

        try:
            self._sender.connect()

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
            self._logger.debug('Found invalid item, probably migrating', e)
            self.disconnect()
            return self.connect(_sync_updates=_sync_updates)

        except (RPCError, ConnectionError) as error:
            # Probably errors from the previous session, ignore them
            self.disconnect()
            self._logger.debug(
                'Could not stabilise initial connection: {}'.format(error)
            )
            return False

    def is_connected(self):
        return self._sender.is_connected()

    def _wrap_init_connection(self, query):
        """Wraps query around InvokeWithLayerRequest(InitConnectionRequest())"""
        return InvokeWithLayerRequest(LAYER, InitConnectionRequest(
            api_id=self.api_id,
            device_model=self.session.device_model,
            system_version=self.session.system_version,
            app_version=self.session.app_version,
            lang_code=self.session.lang_code,
            system_lang_code=self.session.system_lang_code,
            lang_pack='',  # "langPacks are for official apps only"
            query=query
        ))

    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        self._user_connected = False  # This will stop recv_thread's loop
        self.updates.stop_workers()

        # This will trigger a "ConnectionResetError" on the recv_thread,
        # which won't attempt reconnecting as ._user_connected is False.
        self._sender.disconnect()

        if self._recv_thread:
            self._recv_thread.join()

        # TODO Shall we clear the _exported_sessions, or may be reused?
        pass

    def _reconnect(self, new_dc=None):
        """If 'new_dc' is not set, only a call to .connect() will be made
           since it's assumed that the connection has been lost and the
           library is reconnecting.

           If 'new_dc' is set, the client is first disconnected from the
           current data center, clears the auth key for the old DC, and
           connects to the new data center.
        """
        if new_dc is None:
            # Assume we are disconnected due to some error, so connect again
            with self._reconnect_lock:
                # Another thread may have connected again, so check that first
                if self.is_connected():
                    return True

                try:
                    return self.connect()
                except ConnectionResetError:
                    return False
        else:
            # Since we're reconnecting possibly due to a UserMigrateError,
            # we need to first know the Data Centers we can connect to. Do
            # that before disconnecting.
            dc = self._get_dc(new_dc)

            self.session.server_address = dc.ip_address
            self.session.port = dc.port
            # auth_key's are associated with a server, which has now changed
            # so it's not valid anymore. Set to None to force recreating it.
            self.session.auth_key = None
            self.session.save()
            self.disconnect()
            return self.connect()

    # endregion

    # region Working with different connections/Data Centers

    def _on_read_thread(self):
        return self._recv_thread is not None and \
               threading.get_ident() == self._recv_thread.ident

    def _get_dc(self, dc_id, ipv6=False, cdn=False):
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
                if dc.id == dc_id and bool(dc.ipv6) == ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            if not cdn:
                raise

            # New configuration, perhaps a new CDN was added?
            TelegramBareClient._config = self(GetConfigRequest())
            return self._get_dc(dc_id, ipv6=ipv6, cdn=cdn)

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
            export_auth = self(ExportAuthorizationRequest(dc_id))

            # Create a temporary session for this IP address, which needs
            # to be different because each auth_key is unique per DC.
            #
            # Construct this session with the connection parameters
            # (system version, device model...) from the current one.
            session = Session(self.session)
            session.server_address = dc.ip_address
            session.port = dc.port
            self._exported_sessions[dc_id] = session

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
            self._logger.warning('Unknown return export_auth type', export_auth)

        client._authorized = True  # We exported the auth, so we got auth
        return client

    def _get_cdn_client(self, cdn_redirect):
        """Similar to ._get_exported_client, but for CDNs"""
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = Session(self.session)
            session.server_address = dc.ip_address
            session.port = dc.port
            self._exported_sessions[cdn_redirect.dc_id] = session

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
           ValueError().
        """
        if not all(isinstance(x, TLObject) and
                   x.content_related for x in requests):
            raise ValueError('You can only invoke requests, not types!')

        # Determine the sender to be used (main or a new connection)
        on_main_thread = threading.get_ident() == self._main_thread_ident
        if on_main_thread or self._on_read_thread():
            sender = self._sender
            update_state = self.updates
        else:
            sender = self._sender.clone()
            sender.connect()
            # We're on another connection, Telegram will resend all the
            # updates that we haven't acknowledged (potentially entering
            # an infinite loop if we're calling this in response to an
            # update event, as it would be received again and again). So
            # to avoid this we will simply not process updates on these
            # new temporary connections, as they will be sent and later
            # acknowledged over the main connection.
            update_state = None

        # We should call receive from this thread if there's no background
        # thread reading or if the server disconnected us and we're trying
        # to reconnect. This is because the read thread may either be
        # locked also trying to reconnect or we may be said thread already.
        call_receive = not on_main_thread or self._recv_thread is None \
                       or self._reconnect_lock.locked()
        try:
            for _ in range(retries):
                if self._background_error and on_main_thread:
                    raise self._background_error

                result = self._invoke(
                    sender, call_receive, update_state, *requests
                )
                if result is not None:
                    return result

            raise ValueError('Number of retries reached 0.')
        finally:
            if sender != self._sender:
                sender.disconnect()  # Close temporary connections

    # Let people use client.invoke(SomeRequest()) instead client(...)
    invoke = __call__

    def _invoke(self, sender, call_receive, update_state, *requests):
        # We need to specify the new layer (by initializing a new
        # connection) if it has changed from the latest known one.
        init_connection = self.session.layer != LAYER

        try:
            # Ensure that we start with no previous errors (i.e. resending)
            for x in requests:
                x.confirm_received.clear()
                x.rpc_error = None

            if not self.session.auth_key:
                # New key, we need to tell the server we're going to use
                # the latest layer and initialize the connection doing so.
                self.session.auth_key, self.session.time_offset = \
                    authenticator.do_authentication(self._sender.connection)
                init_connection = True

            if init_connection:
                if len(requests) == 1:
                    requests = [self._wrap_init_connection(requests[0])]
                else:
                    # We need a SINGLE request (like GetConfig) to init conn.
                    # Once that's done, the N original requests will be
                    # invoked.
                    TelegramBareClient._config = self(
                        self._wrap_init_connection(GetConfigRequest())
                    )

            sender.send(*requests)

            if not call_receive:
                # TODO This will be slightly troublesome if we allow
                # switching between constant read or not on the fly.
                # Must also watch out for calling .read() from two places,
                # in which case a Lock would be required for .receive().
                for x in requests:
                    x.confirm_received.wait(
                        sender.connection.get_timeout()
                    )
            else:
                while not all(x.confirm_received.is_set() for x in requests):
                    sender.receive(update_state=update_state)

        except BrokenAuthKeyError:
            self._logger.error('Broken auth key, a new one will be generated')
            self.session.auth_key = None

        except TimeoutError:
            pass  # We will just retry

        except ConnectionResetError:
            if not self._user_connected or self._reconnect_lock.locked():
                # Only attempt reconnecting if the user called connect and not
                # reconnecting already.
                raise

            self._logger.debug('Server disconnected us. Reconnecting and '
                               'resending request...')

            if sender != self._sender:
                # TODO Try reconnecting forever too?
                sender.connect()
            else:
                while self._user_connected and not self._reconnect():
                    sleep(0.1)  # Retry forever until we can send the request
            return None

        if init_connection:
            # We initialized the connection successfully, even if
            # a request had an RPC error we have invoked it fine.
            self.session.layer = LAYER
            self.session.save()

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
            self._logger.debug(
                'DC error when invoking request, '
                'attempting to reconnect at DC {}'.format(e.new_dc)
            )

            # TODO What happens with the background thread here?
            # For normal use cases, this won't happen, because this will only
            # be on the very first connection (not authorized, not running),
            # but may be an issue for people who actually travel?
            self._reconnect(new_dc=e.new_dc)
            return self._invoke(sender, call_receive, update_state, *requests)

        except ServerError as e:
            # Telegram is having some issues, just retry
            self._logger.debug(
                '[ERROR] Telegram is having some internal issues', e
            )

        except FloodWaitError as e:
            if e.seconds > self.session.flood_sleep_threshold | 0:
                raise

            self._logger.debug(
                'Sleep of %d seconds below threshold, sleeping' % e.seconds
            )
            sleep(e.seconds)

    # Some really basic functionality

    def is_user_authorized(self):
        """Has the user been authorized yet
           (code request sent and confirmed)?"""
        return self._authorized

    # endregion

    # region Uploading media

    def upload_file(self,
                    file,
                    part_size_kb=None,
                    file_name=None,
                    progress_callback=None):
        """Uploads the specified file and returns a handle (an instance
           of InputFile or InputFileBig, as required) which can be later used.

           Uploading a file will simply return a "handle" to the file stored
           remotely in the Telegram servers, which can be later used on. This
           will NOT upload the file to your own chat.

           'file' may be either a file path, a byte array, or a stream.
           Note that if the file is a stream it will need to be read
           entirely into memory to tell its size first.

           If 'progress_callback' is not None, it should be a function that
           takes two parameters, (bytes_uploaded, total_bytes).

           Default values for the optional parameters if left as None are:
             part_size_kb = get_appropriated_part_size(file_size)
             file_name    = os.path.basename(file_path)
        """
        if isinstance(file, str):
            file_size = os.path.getsize(file)
        elif isinstance(file, bytes):
            file_size = len(file)
        else:
            file = file.read()
            file_size = len(file)

        if not part_size_kb:
            part_size_kb = get_appropriated_part_size(file_size)

        if part_size_kb > 512:
            raise ValueError('The part size must be less or equal to 512KB')

        part_size = int(part_size_kb * 1024)
        if part_size % 1024 != 0:
            raise ValueError('The part size must be evenly divisible by 1024')

        # Determine whether the file is too big (over 10MB) or not
        # Telegram does make a distinction between smaller or larger files
        is_large = file_size > 10 * 1024 * 1024
        part_count = (file_size + part_size - 1) // part_size

        file_id = utils.generate_random_long()
        hash_md5 = md5()

        stream = open(file, 'rb') if isinstance(file, str) else BytesIO(file)
        try:
            for part_index in range(part_count):
                # Read the file by in chunks of size part_size
                part = stream.read(part_size)

                # The SavePartRequest is different depending on whether
                # the file is too large or not (over or less than 10MB)
                if is_large:
                    request = SaveBigFilePartRequest(file_id, part_index,
                                                     part_count, part)
                else:
                    request = SaveFilePartRequest(file_id, part_index, part)

                result = self(request)
                if result:
                    if not is_large:
                        # No need to update the hash if it's a large file
                        hash_md5.update(part)

                    if progress_callback:
                        progress_callback(stream.tell(), file_size)
                else:
                    raise ValueError('Failed to upload file part {}.'
                                     .format(part_index))
        finally:
            stream.close()

        # Set a default file name if None was specified
        if not file_name:
            if isinstance(file, str):
                file_name = os.path.basename(file)
            else:
                file_name = str(file_id)

        if is_large:
            return InputFileBig(file_id, part_count, file_name)
        else:
            return InputFile(file_id, part_count, file_name,
                             md5_checksum=hash_md5.hexdigest())

    # endregion

    # region Downloading media

    def download_file(self,
                      input_location,
                      file,
                      part_size_kb=None,
                      file_size=None,
                      progress_callback=None):
        """Downloads the given InputFileLocation to file (a stream or str).

           If 'progress_callback' is not None, it should be a function that
           takes two parameters, (bytes_downloaded, total_bytes). Note that
           'total_bytes' simply equals 'file_size', and may be None.
        """
        if not part_size_kb:
            if not file_size:
                part_size_kb = 64  # Reasonable default
            else:
                part_size_kb = get_appropriated_part_size(file_size)

        part_size = int(part_size_kb * 1024)
        # https://core.telegram.org/api/files says:
        # > part_size % 1024 = 0 (divisible by 1KB)
        #
        # But https://core.telegram.org/cdn (more recent) says:
        # > limit must be divisible by 4096 bytes
        # So we just stick to the 4096 limit.
        if part_size % 4096 != 0:
            raise ValueError('The part size must be evenly divisible by 4096.')

        if isinstance(file, str):
            # Ensure that we'll be able to download the media
            utils.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        # The used client will change if FileMigrateError occurs
        client = self
        cdn_decrypter = None

        try:
            offset = 0
            while True:
                try:
                    if cdn_decrypter:
                        result = cdn_decrypter.get_file()
                    else:
                        result = client(GetFileRequest(
                            input_location, offset, part_size
                        ))

                        if isinstance(result, FileCdnRedirect):
                            cdn_decrypter, result = \
                                CdnDecrypter.prepare_decrypter(
                                    client, self._get_cdn_client(result), result
                                )

                except FileMigrateError as e:
                    client = self._get_exported_client(e.new_dc)
                    continue

                offset += part_size

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    # Return some extra information, unless it's a CDN file
                    return getattr(result, 'type', '')

                f.write(result.bytes)
                if progress_callback:
                    progress_callback(f.tell(), file_size)
        finally:
            if client != self:
                client.disconnect()

            if cdn_decrypter:
                try:
                    cdn_decrypter.client.disconnect()
                except:
                    pass
            if isinstance(file, str):
                f.close()

    # endregion

    # region Updates handling

    def sync_updates(self):
        """Synchronizes self.updates to their initial state. Will be
           called automatically on connection if self.updates.enabled = True,
           otherwise it should be called manually after enabling updates.
        """
        self.updates.process(self(GetStateRequest()))

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        if self.updates.workers is None:
            warnings.warn(
                "You have not setup any workers, so you won't receive updates."
                " Pass update_workers=4 when creating the TelegramClient,"
                " or set client.self.updates.workers = 4"
            )

        self.updates.handlers.append(handler)

    def remove_update_handler(self, handler):
        self.updates.handlers.remove(handler)

    def list_update_handlers(self):
        return self.updates.handlers[:]

    # endregion

    # Constant read

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
            self._logger.debug('Forcing exit...')
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
            raise ValueError('Can only idle if spawn_read_thread=False')

        for sig in stop_signals:
            signal(sig, self._signal_handler)

        while self._user_connected:
            try:
                if datetime.now() > self._last_ping + self._ping_delay:
                    self._sender.send(PingRequest(
                        int.from_bytes(os.urandom(8), 'big', signed=True)
                    ))
                    self._last_ping = datetime.now()

                self._sender.receive(update_state=self.updates)
            except TimeoutError:
                # No problem.
                pass
            except ConnectionResetError:
                self._logger.debug('Server disconnected us. Reconnecting...')
                while self._user_connected and not self._reconnect():
                    sleep(0.1)  # Retry forever, this is instant messaging

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
                # Unknown exception, pass it to the main thread
                self._logger.error(
                    'Unknown error on the read thread, please report',
                    error
                )

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
                    "Not using PySocks, so it can't be a socket error"

                # If something strange happens we don't want to enter an
                # infinite loop where all we do is raise an exception, so
                # add a little sleep to avoid the CPU usage going mad.
                sleep(0.1)

        self._recv_thread = None

    # endregion
