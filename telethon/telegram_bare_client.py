import logging
from time import sleep
from datetime import timedelta
from hashlib import md5
from os import path
from io import BytesIO

# Import some externalized utilities to work with the Telegram types and more
from . import helpers as utils
from .errors import (
    RPCError, FloodWaitError, FileMigrateError, TypeNotFoundError
)
from .network import authenticator, MtProtoSender, Connection, ConnectionMode
from .utils import get_appropriated_part_size
from .crypto import rsa, CdnDecrypter

# For sending and receiving requests
from .tl import TLObject, Session
from .tl.all_tlobjects import layer
from .tl.functions import (
    InitConnectionRequest, InvokeWithLayerRequest, PingRequest
)

# Initial request
from .tl.functions.help import GetConfigRequest
from .tl.functions.auth import (
    ImportAuthorizationRequest, ExportAuthorizationRequest
)

# Easier access for working with media
from .tl.functions.upload import (
    GetFileRequest, GetCdnFileRequest, ReuploadCdnFileRequest,
    SaveBigFilePartRequest, SaveFilePartRequest
)

from .tl.functions.help import GetCdnConfigRequest

# All the types we need to work with
from .tl.types import InputFile, InputFileBig
from .tl.types.upload import FileCdnRedirect, CdnFileReuploadNeeded


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
    __version__ = '0.13'

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 connection_mode=ConnectionMode.TCP_FULL,
                 proxy=None, timeout=timedelta(seconds=5)):
        """Initializes the Telegram client with the specified API ID and Hash.
           Session must always be a Session instance, and an optional proxy
           can also be specified to be used on the connection.
        """
        self.session = session
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self._connection_mode = connection_mode
        self.proxy = proxy
        self._timeout = timeout
        self._logger = logging.getLogger(__name__)

        # Cache "exported" senders 'dc_id: TelegramBareClient' and
        # their corresponding sessions not to recreate them all
        # the time since it's a (somewhat expensive) process.
        self._cached_clients = {}

        # Update callbacks (functions accepting a single TLObject) go here
        #
        # Note that changing the list to which this variable points to
        # will not reflect the changes on the existing senders.
        self._update_callbacks = []

        # These will be set later
        self.dc_options = None
        self._sender = None

    # endregion

    # region Connecting

    def connect(self, exported_auth=None, initial_query=None):
        """Connects to the Telegram servers, executing authentication if
           required. Note that authenticating to the Telegram servers is
           not the same as authenticating the desired user itself, which
           may require a call (or several) to 'sign_in' for the first time.

           If 'exported_auth' is not None, it will be used instead to
           determine the authorization key for the current session.

           If 'initial_query' is not None, it will override the default
           'GetConfigRequest()', and its result will be returned ONLY
           if the client wasn't connected already.
        """
        if self._sender and self._sender.is_connected():
            # Try sending a ping to make sure we're connected already
            # TODO Maybe there's a better way to check this
            try:
                if initial_query is None:
                    self(PingRequest(utils.generate_random_long()))
                    return True
                else:
                    return self(initial_query)
            except:
                # If ping failed, ensure we're disconnected first
                self.disconnect()

        connection = Connection(
            self.session.server_address, self.session.port,
            mode=self._connection_mode, proxy=self.proxy, timeout=self._timeout
        )

        try:
            if not self.session.auth_key:
                self.session.auth_key, self.session.time_offset = \
                    authenticator.do_authentication(connection)

                self.session.save()

            self._sender = MtProtoSender(connection, self.session)
            self._sender.unhandled_callbacks = self._update_callbacks
            self._sender.connect()

            # Now it's time to send an InitConnectionRequest
            # This must always be invoked with the layer we'll be using
            if exported_auth is None:
                query = initial_query if initial_query else GetConfigRequest()
            else:
                query = ImportAuthorizationRequest(
                    exported_auth.id, exported_auth.bytes)

            request = InitConnectionRequest(
                api_id=self.api_id,
                device_model=self.session.device_model,
                system_version=self.session.system_version,
                app_version=self.session.app_version,
                lang_code=self.session.lang_code,
                system_lang_code=self.session.system_lang_code,
                lang_pack='',  # "langPacks are for official apps only"
                query=query)

            result = self(InvokeWithLayerRequest(
                layer=layer, query=request
            ))

            if initial_query is None:
                if exported_auth is not None:
                    result = self(GetConfigRequest())

                # We're only interested in the DC options,
                # although many other options are available!
                self.dc_options = result.dc_options
                return True
            else:
                return result

        except TypeNotFoundError as e:
            # This is fine, probably layer migration
            self._logger.debug('Found invalid item, probably migrating', e)
            self.disconnect()
            return self.connect(exported_auth=exported_auth,
                                initial_query=initial_query)

        except (RPCError, ConnectionError) as error:
            # Probably errors from the previous session, ignore them
            self.disconnect()
            self._logger.debug('Could not stabilise initial connection: {}'
                                 .format(error))
            return None if initial_query else False

    def disconnect(self):
        """Disconnects from the Telegram server"""
        if self._sender:
            self._sender.disconnect()
            self._sender = None

    def reconnect(self, new_dc=None):
        """Disconnects and connects again (effectively reconnecting).

           If 'new_dc' is not None, the current authorization key is
           removed, the DC used is switched, and a new connection is made.
        """
        self.disconnect()

        if new_dc is not None:
            self.session.auth_key = None  # Force creating new auth_key
            dc = self._get_dc(new_dc)
            self.session.server_address = dc.ip_address
            self.session.port = dc.port
            self.session.save()

        self.connect()

    # endregion

    # region Working with different Data Centers

    def _get_dc(self, dc_id, ipv6=False, cdn=False):
        """Gets the Data Center (DC) associated to 'dc_id'"""
        if not self.dc_options:
            raise ConnectionError(
                'Cannot determine the required data center IP address. '
                'Stabilise a successful initial connection first.')

        try:
            return next(
                dc for dc in self.dc_options if dc.id == dc_id and
                bool(dc.ipv6) == ipv6 and bool(dc.cdn) == cdn
            )
        except StopIteration:
            if not cdn:
                raise

            for pk in self(GetCdnConfigRequest()).public_keys:
                rsa.add_key(pk.public_key)

            self.dc_options = self(GetConfigRequest()).dc_options
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
                timeout=self._timeout
            )
            client.connect(exported_auth=export_auth)

            if not bypass_cache:
                # Don't go through this expensive process every time.
                self._cached_clients[dc_id] = client
            return client

    # endregion

    # region Invoking Telegram requests

    def invoke(self, request, updates=None, call_receive=True):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           If 'updates' is not None, all read update object will be put
           in such list. Otherwise, update objects will be ignored.

           If 'call_receive' is set to False, then there should be another
           thread calling to 'self._sender.receive()' running or this method
           will lock forever.
        """
        if not isinstance(request, TLObject) and not request.content_related:
            raise ValueError('You can only invoke requests, not types!')

        if not self._sender:
            raise ValueError('You must be connected to invoke requests!')

        try:
            # Ensure that we start with no previous errors (i.e. resending)
            request.confirm_received.clear()
            request.rpc_error = None

            self._sender.send(request)
            if not call_receive:
                # TODO This will be slightly troublesome if we allow
                # switching between constant read or not on the fly.
                # Must also watch out for calling .read() from two places,
                # in which case a Lock would be required for .receive().
                request.confirm_received.wait()  # TODO Socket's timeout here?
            else:
                while not request.confirm_received.is_set():
                    self._sender.receive()

            if request.rpc_error:
                raise request.rpc_error
            return request.result

        except ConnectionResetError:
            self._logger.debug('Server disconnected us. Reconnecting and '
                               'resending request...')
            self.reconnect()
            return self.invoke(request)

        except FloodWaitError:
            self.disconnect()
            raise

    # Let people use client(SomeRequest()) instead client.invoke(...)
    __call__ = invoke

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
             file_name    = path.basename(file_path)
        """
        if isinstance(file, str):
            file_size = path.getsize(file)
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
                file_name = path.basename(file)
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
                        result = cdn_decrypter.get_file(offset, part_size)
                    else:
                        result = client(GetFileRequest(
                            input_location, offset, part_size
                        ))

                        if isinstance(result, FileCdnRedirect):
                            cdn_decrypter, result = \
                                CdnDecrypter.prepare_decrypter(
                                    client, TelegramBareClient, result,
                                    offset, part_size
                            )

                except FileMigrateError as e:
                    client = self._get_exported_client(e.new_dc)
                    continue

                offset_index += 1

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    if cdn_decrypter:
                        cdn_decrypter.finish_check()

                    # Return some extra information, unless it's a CDN file
                    return getattr(result, 'type', '')

                f.write(result.bytes)
                if progress_callback:
                    progress_callback(f.tell(), file_size)
        finally:
            if cdn_decrypter:
                try: cdn_decrypter.client.disconnect()
                except: pass
            if isinstance(file, str):
                f.close()

    # endregion
