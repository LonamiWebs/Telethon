import logging
import os
import threading
from datetime import timedelta, datetime
from hashlib import md5
from io import BytesIO
from threading import Lock
from time import sleep

from . import helpers as utils
from .crypto import rsa, CdnDecrypter
from .errors import (
    RPCError, BrokenAuthKeyError,
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
    __version__ = '0.14.2'

    # TODO Make this thread-safe, all connections share the same DC
    _dc_options = None

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 connection_mode=ConnectionMode.TCP_FULL,
                 proxy=None,
                 process_updates=False,
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

        self._sender = MtProtoSender(self.session, Connection(
            self.session.server_address, self.session.port,
            mode=connection_mode, proxy=proxy, timeout=timeout
        ))

        self._logger = logging.getLogger(__name__)

        # Two threads may be calling reconnect() when the connection is lost,
        # we only want one to actually perform the reconnection.
        self._connect_lock = Lock()

        # Cache "exported" senders 'dc_id: TelegramBareClient' and
        # their corresponding sessions not to recreate them all
        # the time since it's a (somewhat expensive) process.
        self._cached_clients = {}

        # This member will process updates if enabled.
        # One may change self.updates.enabled at any later point.
        self.updates = UpdateState(process_updates)

        # Used on connection - the user may modify these and reconnect
        kwargs['app_version'] = kwargs.get('app_version', self.__version__)
        for name, value in kwargs.items():
            if hasattr(self.session, name):
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
        self._authorized = False

        # Uploaded files cache so subsequent calls are instant
        self._upload_cache = {}

        # Constantly read for results and updates from within the main client
        self._recv_thread = None

        # Identifier of the main thread (the one that called .connect()).
        # This will be used to create new connections from any other thread,
        # so that requests can be sent in parallel.
        self._main_thread_ident = None

        # Default PingRequest delay
        self._last_ping = datetime.now()
        self._ping_delay = timedelta(minutes=1)

    # endregion

    # region Connecting

    def connect(self, exported_auth=None):
        """Connects to the Telegram servers, executing authentication if
           required. Note that authenticating to the Telegram servers is
           not the same as authenticating the desired user itself, which
           may require a call (or several) to 'sign_in' for the first time.

           If 'exported_auth' is not None, it will be used instead to
           determine the authorization key for the current session.
        """
        self._main_thread_ident = threading.get_ident()

        try:
            self._sender.connect()
            if not self.session.auth_key:
                # New key, we need to tell the server we're going to use
                # the latest layer
                try:
                    self.session.auth_key, self.session.time_offset = \
                        authenticator.do_authentication(self._sender.connection)
                except BrokenAuthKeyError:
                    return False

                self.session.layer = LAYER
                self.session.save()
                init_connection = True
            else:
                init_connection = self.session.layer != LAYER

            if init_connection:
                if exported_auth is not None:
                    self._init_connection(ImportAuthorizationRequest(
                        exported_auth.id, exported_auth.bytes
                    ))
                else:
                    TelegramBareClient._dc_options = \
                        self._init_connection(GetConfigRequest()).dc_options

            elif exported_auth is not None:
                self(ImportAuthorizationRequest(
                    exported_auth.id, exported_auth.bytes
                ))

            if TelegramBareClient._dc_options is None:
                TelegramBareClient._dc_options = \
                    self(GetConfigRequest()).dc_options

            # Connection was successful! Try syncing the update state
            # to also assert whether the user is logged in or not.
            self._user_connected = True
            try:
                self.sync_updates()
                self._set_connected_and_authorized()
            except UnauthorizedError:
                self._authorized = False

            return True

        except TypeNotFoundError as e:
            # This is fine, probably layer migration
            self._logger.debug('Found invalid item, probably migrating', e)
            self.disconnect()
            return self.connect(exported_auth=exported_auth)

        except (RPCError, ConnectionError) as error:
            # Probably errors from the previous session, ignore them
            self.disconnect()
            self._logger.debug(
                'Could not stabilise initial connection: {}'.format(error)
            )
            return False

    def is_connected(self):
        return self._sender.is_connected()

    def _init_connection(self, query=None):
        result = self(InvokeWithLayerRequest(LAYER, InitConnectionRequest(
            api_id=self.api_id,
            device_model=self.session.device_model,
            system_version=self.session.system_version,
            app_version=self.session.app_version,
            lang_code=self.session.lang_code,
            system_lang_code=self.session.system_lang_code,
            lang_pack='',  # "langPacks are for official apps only"
            query=query
        )))
        self.session.layer = LAYER
        self.session.save()
        return result

    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        self._user_connected = False
        self._recv_thread = None

        # This will trigger a "ConnectionResetError", for subsequent calls
        # to read or send (from another thread) and usually, the background
        # thread would try restarting the connection but since the
        # ._recv_thread = None, it knows it doesn't have to.
        self._sender.disconnect()

        # Also disconnect all the cached senders
        for sender in self._cached_clients.values():
            sender.disconnect()

        self._cached_clients.clear()

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
            with self._connect_lock:
                # Another thread may have connected again, so check that first
                if not self.is_connected():
                    return self.connect()
                else:
                    return True
        else:
            self.disconnect()
            self.session.auth_key = None  # Force creating new auth_key
            dc = self._get_dc(new_dc)
            ip = dc.ip_address
            self._sender.connection.ip = self.session.server_address = ip
            self._sender.connection.port = self.session.port = dc.port
            self.session.save()
            return self.connect()

    # endregion

    # region Working with different connections/Data Centers

    def _on_read_thread(self):
        return self._recv_thread is not None and \
               threading.get_ident() == self._recv_thread.ident

    def _get_dc(self, dc_id, ipv6=False, cdn=False):
        """Gets the Data Center (DC) associated to 'dc_id'"""
        if TelegramBareClient._dc_options is None:
            raise ConnectionError(
                'Cannot determine the required data center IP address. '
                'Stabilise a successful initial connection first.')

        try:
            if cdn:
                # Ensure we have the latest keys for the CDNs
                for pk in self(GetCdnConfigRequest()).public_keys:
                    rsa.add_key(pk.public_key)

            return next(
                dc for dc in TelegramBareClient._dc_options if dc.id == dc_id
                and bool(dc.ipv6) == ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            if not cdn:
                raise

            # New configuration, perhaps a new CDN was added?
            TelegramBareClient._dc_options = self(GetConfigRequest()).dc_options
            return self._get_dc(dc_id, ipv6=ipv6, cdn=cdn)

    def _get_exported_client(self, dc_id,
                             init_connection=False,
                             bypass_cache=False):
        """Gets a cached exported TelegramBareClient for the desired DC.

           If it's the first time retrieving the TelegramBareClient, the
           current authorization is exported to the new DC so that
           it can be used there, and the connection is initialized.

           If after using the sender a ConnectionResetError is raised,
           this method should be called again with init_connection=True
           in order to perform the reconnection.

           If bypass_cache is True, a new client will be exported and
           it will not be cached.
        """
        # Thanks badoualy/kotlogram on /telegram/api/DefaultTelegramClient.kt
        # for clearly showing how to export the authorization! ^^
        client = self._cached_clients.get(dc_id)
        if client and not bypass_cache:
            if init_connection:
                client.reconnect()
            return client
        else:
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
            client = TelegramBareClient(
                session, self.api_id, self.api_hash,
                proxy=self._sender.connection.conn.proxy,
                timeout=self._sender.connection.get_timeout()
            )
            client.connect(exported_auth=export_auth)

            if not bypass_cache:
                # Don't go through this expensive process every time.
                self._cached_clients[dc_id] = client
            return client

    # endregion

    # region Invoking Telegram requests

    def invoke(self, *requests, call_receive=True, retries=5):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           The invoke will be retried up to 'retries' times before raising
           ValueError().
        """
        # This is only valid when the read thread is reconnecting,
        # that is, the connection lock is locked.
        on_read_thread = self._on_read_thread()
        if on_read_thread and not self._connect_lock.locked():
            return  # Just ignore, we would be raising and crashing the thread

        # Any error from a background thread will be "posted" and checked here
        self.updates.check_error()

        if not all(isinstance(x, TLObject) and
                   x.content_related for x in requests):
            raise ValueError('You can only invoke requests, not types!')

        if retries <= 0:
            raise ValueError('Number of retries reached 0.')

        # Determine the sender to be used (main or a new connection)
        # TODO Polish this so it's nicer
        on_main_thread = threading.get_ident() == self._main_thread_ident
        if on_main_thread or on_read_thread:
            sender = self._sender
        else:
            conn = Connection(
                self.session.server_address, self.session.port,
                mode=self._sender.connection._mode,
                proxy=self._sender.connection.conn.proxy,
                timeout=self._sender.connection.get_timeout()
            )
            sender = MtProtoSender(self.session, conn)
            sender.connect()

        try:
            # Ensure that we start with no previous errors (i.e. resending)
            for x in requests:
                x.confirm_received.clear()
                x.rpc_error = None

            sender.send(*requests)

            # We should call receive from this thread if there's no background
            # thread reading or if the server disconnected us and we're trying
            # to reconnect. This is because the read thread may either be
            # locked also trying to reconnect or we may be said thread already.
            call_receive = not on_main_thread or \
                self._recv_thread is None or self._connect_lock.locked()

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
                    sender.receive(update_state=self.updates)

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
            return self.invoke(
                *requests, call_receive=call_receive, retries=(retries - 1)
            )

        except TimeoutError:
            pass  # We will just retry

        except ConnectionResetError:
            if self._connect_lock.locked():
                # We are connecting and we don't want to reconnect there...
                raise

            self._logger.debug('Server disconnected us. Reconnecting and '
                               'resending request...')

            if sender != self._sender:
                # TODO Try reconnecting forever too?
                sender.connect()
            else:
                while self._user_connected and not self._reconnect():
                    sleep(0.1)  # Retry forever until we can send the request

        except FloodWaitError:
            sender.disconnect()
            self.disconnect()
            raise

        finally:
            if sender != self._sender:
                sender.disconnect()

        try:
            raise next(x.rpc_error for x in requests if x.rpc_error)
        except StopIteration:
            if any(x.result is None for x in requests):
                # "A container may only be accepted or
                #  rejected by the other party as a whole."
                return self.invoke(
                    *requests, call_receive=call_receive, retries=(retries - 1)
                )
            elif len(requests) == 1:
                return requests[0].result
            else:
                return [x.result for x in requests]

    # Let people use client(SomeRequest()) instead client.invoke(...)
    __call__ = invoke

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
            offset_index = 0
            while True:
                offset = offset_index * part_size

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
                                    client, TelegramBareClient, result
                                )

                except FileMigrateError as e:
                    client = self._get_exported_client(e.new_dc)
                    continue

                offset_index += 1

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    # Return some extra information, unless it's a CDN file
                    return getattr(result, 'type', '')

                f.write(result.bytes)
                if progress_callback:
                    progress_callback(f.tell(), file_size)
        finally:
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
        sync = not self.updates.handlers
        self.updates.handlers.append(handler)
        if sync:
            self.sync_updates()

    def remove_update_handler(self, handler):
        self.updates.handlers.remove(handler)

    def list_update_handlers(self):
        return self.updates.handlers[:]

    # endregion

    # Constant read

    def _set_connected_and_authorized(self):
        self._authorized = True
        if self._recv_thread is None:
            self._recv_thread = threading.Thread(
                name='ReadThread', daemon=True,
                target=self._recv_thread_impl
            )
            self._recv_thread.start()

    # By using this approach, another thread will be
    # created and started upon connection to constantly read
    # from the other end. Otherwise, manual calls to .receive()
    # must be performed. The MtProtoSender cannot be connected,
    # or an error will be thrown.
    #
    # This way, sending and receiving will be completely independent.
    def _recv_thread_impl(self):
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

            except Exception as e:
                # Unknown exception, pass it to the main thread
                self.updates.set_error(e)
                break

        self._recv_thread = None

    # endregion
