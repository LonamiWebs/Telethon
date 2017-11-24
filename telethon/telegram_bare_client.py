import logging
import os
import asyncio
from datetime import timedelta
from hashlib import md5
from io import BytesIO
from asyncio import Lock

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


DEFAULT_IPV4_IP = '149.154.167.51'
DEFAULT_IPV6_IP = '[2001:67c:4e8:f002::a]'
DEFAULT_PORT = 443


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
                 timeout=timedelta(seconds=5),
                 loop=None,
                 **kwargs):
        """Refer to TelegramClient.__init__ for docs on this method"""
        if not api_id or not api_hash:
            raise PermissionError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to Telethon's README.rst for more information.")

        self._use_ipv6 = use_ipv6
        
        # Determine what session object we have
        if isinstance(session, str) or session is None:
            session = Session.try_load_or_create_new(session)
        elif not isinstance(session, Session):
            raise ValueError(
                'The given session must be a str or a Session instance.'
            )

        self._loop = loop if loop else asyncio.get_event_loop()

        # ':' in session.server_address is True if it's an IPv6 address
        if (not session.server_address or
                (':' in session.server_address) != use_ipv6):
            session.port = DEFAULT_PORT
            session.server_address = \
                DEFAULT_IPV6_IP if self._use_ipv6 else DEFAULT_IPV4_IP

        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash
        if self.api_id < 20:  # official apps must use obfuscated
            connection_mode = ConnectionMode.TCP_OBFUSCATED

        # This is the main sender, which will be used from the thread
        # that calls .connect(). Every other thread will spawn a new
        # temporary connection. The connection on this one is always
        # kept open so Telegram can send us updates.
        self._sender = MtProtoSender(
            self.session,
            Connection(mode=connection_mode, proxy=proxy, timeout=timeout, loop=self._loop),
            self._loop
        )

        self._logger = logging.getLogger(__name__)

        # Two coroutines may be calling reconnect() when the connection is lost,
        # we only want one to actually perform the reconnection.
        self._reconnect_lock = Lock(loop=self._loop)

        # Cache "exported" sessions as 'dc_id: Session' not to recreate
        # them all the time since generating a new key is a relatively
        # expensive operation.
        self._exported_sessions = {}

        # This member will process updates if enabled.
        # One may change self.updates.enabled at any later point.
        self.updates = UpdateState(self._loop)

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

        self._recv_loop = None
        self._ping_loop = None

        # Default PingRequest delay
        self._ping_delay = timedelta(minutes=1)

    # endregion

    # region Connecting

    async def connect(self, _sync_updates=True):
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
        try:
            await self._sender.connect()

            # Connection was successful! Try syncing the update state
            # UNLESS '_sync_updates' is False (we probably are in
            # another data center and this would raise UserMigrateError)
            # to also assert whether the user is logged in or not.
            self._user_connected = True
            if self._authorized is None and _sync_updates:
                try:
                    await self.sync_updates()
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
            return await self.connect(_sync_updates=_sync_updates)

        except (RPCError, ConnectionError):
            # Probably errors from the previous session, ignore them
            self.disconnect()
            self._logger.exception('Could not stabilise initial connection.')
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
        """Disconnects from the Telegram server"""
        self._user_connected = False
        self._sender.disconnect()
        # TODO Shall we clear the _exported_sessions, or may be reused?
        pass

    async def _reconnect(self, new_dc=None):
        """If 'new_dc' is not set, only a call to .connect() will be made
           since it's assumed that the connection has been lost and the
           library is reconnecting.

           If 'new_dc' is set, the client is first disconnected from the
           current data center, clears the auth key for the old DC, and
           connects to the new data center.
        """
        if new_dc is None:
            # Assume we are disconnected due to some error, so connect again
            try:
                await self._reconnect_lock.acquire()
                if self.is_connected():
                    return True

                return await self.connect()
            except ConnectionResetError:
                return False
            finally:
                self._reconnect_lock.release()
        else:
            # Since we're reconnecting possibly due to a UserMigrateError,
            # we need to first know the Data Centers we can connect to. Do
            # that before disconnecting.
            dc = await self._get_dc(new_dc)

            self.session.server_address = dc.ip_address
            self.session.port = dc.port
            # auth_key's are associated with a server, which has now changed
            # so it's not valid anymore. Set to None to force recreating it.
            self.session.auth_key = None
            self.session.save()
            self.disconnect()
            return await self.connect()

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
        session = self._exported_sessions.get(dc_id)
        if session:
            export_auth = None  # Already bound with the auth key
        else:
            # TODO Add a lock, don't allow two threads to create an auth key
            # (when calling .connect() if there wasn't a previous session).
            # for the same data center.
            dc = await self._get_dc(dc_id)

            # Export the current authorization to the new DC.
            export_auth = await self(ExportAuthorizationRequest(dc_id))

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
            timeout=self._sender.connection.get_timeout(),
            loop=self._loop
        )
        await client.connect(_sync_updates=False)
        if isinstance(export_auth, ExportedAuthorization):
            await client(ImportAuthorizationRequest(
                id=export_auth.id, bytes=export_auth.bytes
            ))
        elif export_auth is not None:
            self._logger.warning('Unknown return export_auth type', export_auth)

        client._authorized = True  # We exported the auth, so we got auth
        return client

    async def _get_cdn_client(self, cdn_redirect):
        """Similar to ._get_exported_client, but for CDNs"""
        session = self._exported_sessions.get(cdn_redirect.dc_id)
        if not session:
            dc = await self._get_dc(cdn_redirect.dc_id, cdn=True)
            session = Session(self.session)
            session.server_address = dc.ip_address
            session.port = dc.port
            self._exported_sessions[cdn_redirect.dc_id] = session

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
        await client.connect(_sync_updates=False)
        client._authorized = self._authorized
        return client

    # endregion

    # region Invoking Telegram requests

    async def __call__(self, *requests, retries=5):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           The invoke will be retried up to 'retries' times before raising
           ValueError().
        """
        if not all(isinstance(x, TLObject) and
                   x.content_related for x in requests):
            raise ValueError('You can only invoke requests, not types!')

        # We should call receive from this thread if there's no background
        # thread reading or if the server disconnected us and we're trying
        # to reconnect. This is because the read thread may either be
        # locked also trying to reconnect or we may be said thread already.
        call_receive = self._recv_loop is None

        for retry in range(retries):
            result = await self._invoke(call_receive, retry, *requests)
            if result is not None:
                return result

            await asyncio.sleep(retry + 1, loop=self._loop)
            self._logger.debug('RPC failed. Attempting reconnection.')
            if not self._reconnect_lock.locked():
                with await self._reconnect_lock:
                    self._reconnect()

        raise ValueError('Number of retries reached 0.')

    # Let people use client.invoke(SomeRequest()) instead client(...)
    invoke = __call__

    async def _invoke(self, call_receive, retry, *requests):
        # We need to specify the new layer (by initializing a new
        # connection) if it has changed from the latest known one.
        init_connection = self.session.layer != LAYER

        try:
            # Ensure that we start with no previous errors (i.e. resending)
            for x in requests:
                x.rpc_error = None

            if not self.session.auth_key:
                # New key, we need to tell the server we're going to use
                # the latest layer and initialize the connection doing so.
                self.session.auth_key, self.session.time_offset = \
                    await authenticator.do_authentication(self._sender.connection)
                init_connection = True

            if init_connection:
                if len(requests) == 1:
                    requests = [self._wrap_init_connection(requests[0])]
                else:
                    # We need a SINGLE request (like GetConfig) to init conn.
                    # Once that's done, the N original requests will be
                    # invoked.
                    TelegramBareClient._config = await self(
                        self._wrap_init_connection(GetConfigRequest())
                    )

            await self._sender.send(*requests)

            if not call_receive:
                await asyncio.wait(
                    list(map(lambda x: x.confirm_received.wait(), requests)),
                    timeout=self._sender.connection.get_timeout(),
                    loop=self._loop
                )
            else:
                while not all(x.confirm_received.is_set() for x in requests):
                    await self._sender.receive(update_state=self.updates)

        except BrokenAuthKeyError:
            self._logger.error('Broken auth key, a new one will be generated')
            self.session.auth_key = None

        except TimeoutError:
            pass  # We will just retry

        except ConnectionResetError:
            if self._user_connected:
                # Server disconnected us, __call__ will try reconnecting.
                return None
            else:
                # User never called .connect(), so raise this error.
                raise

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

            await self._reconnect(new_dc=e.new_dc)
            return None

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
            await asyncio.sleep(e.seconds, loop=self._loop)
            return None

    # Some really basic functionality

    def is_user_authorized(self):
        """Has the user been authorized yet
           (code request sent and confirmed)?"""
        return self._authorized

    # endregion

    # region Uploading media

    async def upload_file(self,
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

                result = await self(request)
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

    async def download_file(self,
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
                        result = await cdn_decrypter.get_file()
                    else:
                        result = await client(GetFileRequest(
                            input_location, offset, part_size
                        ))

                        if isinstance(result, FileCdnRedirect):
                            cdn_decrypter, result = \
                                await CdnDecrypter.prepare_decrypter(
                                    client,
                                    await self._get_cdn_client(result),
                                    result
                                )

                except FileMigrateError as e:
                    client = await self._get_exported_client(e.new_dc)
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

    async def sync_updates(self):
        """Synchronizes self.updates to their initial state. Will be
           called automatically on connection if self.updates.enabled = True,
           otherwise it should be called manually after enabling updates.
        """
        self.updates.process(await self(GetStateRequest()))

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        self.updates.handlers.append(handler)

    def remove_update_handler(self, handler):
        self.updates.handlers.remove(handler)

    def list_update_handlers(self):
        return self.updates.handlers[:]

    # endregion

    # Constant read

    def _set_connected_and_authorized(self):
        self._authorized = True
        if self._recv_loop is None:
            self._recv_loop = asyncio.ensure_future(self._recv_loop_impl(), loop=self._loop)
        if self._ping_loop is None:
            self._ping_loop = asyncio.ensure_future(self._ping_loop_impl(), loop=self._loop)

    async def _ping_loop_impl(self):
        while self._user_connected:
            await self(PingRequest(int.from_bytes(os.urandom(8), 'big', signed=True)))
            await asyncio.sleep(self._ping_delay.seconds, loop=self._loop)
        self._ping_loop = None

    async def _recv_loop_impl(self):
        need_reconnect = False
        while self._user_connected:
            try:
                if need_reconnect:
                    need_reconnect = False
                    while self._user_connected and not await self._reconnect():
                        # Retry forever, this is instant messaging
                        await asyncio.sleep(0.1, loop=self._loop)

                await self._sender.receive(update_state=self.updates)
            except TimeoutError:
                # No problem.
                pass
            except ConnectionError as error:
                self._logger.debug(error)
                need_reconnect = True
                await asyncio.sleep(1, loop=self._loop)
            except Exception as error:
                # Unknown exception, pass it to the main thread
                self._logger.exception(
                    'Unknown error on the read loop, please report.'
                )

                try:
                    import socks
                    if isinstance(error, (
                            socks.GeneralProxyError,
                            socks.ProxyConnectionError
                    )):
                        # This is a known error, and it's not related to
                        # Telegram but rather to the proxy. Disconnect and
                        # hand it over to the main thread.
                        self._background_error = error
                        self.disconnect()
                        break
                except ImportError:
                    "Not using PySocks, so it can't be a socket error"

                break

        self._recv_loop = None

    # endregion
