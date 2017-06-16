from datetime import timedelta
from mimetypes import guess_type
from threading import Event, RLock, Thread
from time import sleep

from . import TelegramBareClient

# Import some externalized utilities to work with the Telegram types and more
from . import helpers as utils
from .errors import (RPCError, UnauthorizedError, InvalidParameterError,
                     ReadCancelledError, FileMigrateError, PhoneMigrateError,
                     NetworkMigrateError, UserMigrateError, PhoneCodeEmptyError,
                     PhoneCodeExpiredError, PhoneCodeHashEmptyError,
                     PhoneCodeInvalidError, InvalidChecksumError)

# For sending and receiving requests
from .tl import MTProtoRequest, Session, JsonSession

# Required to get the password salt
from .tl.functions.account import GetPasswordRequest

# Logging in and out
from .tl.functions.auth import (CheckPasswordRequest, LogOutRequest,
                                SendCodeRequest, SignInRequest,
                                SignUpRequest, ImportBotAuthorizationRequest)

# Required to work with different data centers
from .tl.functions.auth import ExportAuthorizationRequest

# Easier access to common methods
from .tl.functions.messages import (
    GetDialogsRequest, GetHistoryRequest, ReadHistoryRequest, SendMediaRequest,
    SendMessageRequest)

# For .get_me() and ensuring we're authorized
from .tl.functions.users import GetUsersRequest

# All the types we need to work with
from .tl.types import (
    ChatPhotoEmpty, DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    UserProfilePhotoEmpty, InputUserSelf)

from .utils import find_user_or_chat, get_input_peer, get_extension


class TelegramClient(TelegramBareClient):
    """Full featured TelegramClient meant to extend the basic functionality -

       As opposed to the TelegramBareClient, this one  features downloading
       media from different data centers, starting a second thread to
       handle updates, and some very common functionality.

       This should be used when the (slight) overhead of having locks,
       threads, and possibly multiple connections is not an issue.
    """

    # region Initialization

    def __init__(self, session, api_id, api_hash, proxy=None,
                 device_model=None, system_version=None,
                 app_version=None, lang_code=None):
        """Initializes the Telegram client with the specified API ID and Hash.

           Session can either be a `str` object (filename for the .session)
           or it can be a `Session` instance (in which case list_sessions()
           would probably not work). Pass 'None' for it to be a temporary
           session - remember to '.log_out()'!

           Default values for the optional parameters if left as None are:
             device_model   = platform.node()
             system_version = platform.system()
             app_version    = TelegramClient.__version__
             lang_code      = 'en'
        """

        if not api_id or not api_hash:
            raise PermissionError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to Telethon's README.rst for more information.")

        # Determine what session object we have
        # TODO JsonSession until migration is complete (by v1.0)
        if isinstance(session, str) or session is None:
            session = JsonSession.try_load_or_create_new(session)
        elif not isinstance(session, Session):
            raise ValueError(
                'The given session must be a str or a Session instance.')

        super().__init__(session, api_id, api_hash, proxy)

        # Safety across multiple threads (for the updates thread)
        self._lock = RLock()

        # Methods to be called when an update is received
        self._update_handlers = []
        self._updates_thread_running = Event()
        self._updates_thread_receiving = Event()

        # Used on connection - the user may modify these and reconnect
        if device_model:
            self.session.device_model = device_model

        if system_version:
            self.session.system_version = system_version

        self.session.app_version = \
            app_version if app_version else self.__version__

        if lang_code:
            self.session.lang_code = lang_code

        # Cache "exported" senders 'dc_id: MtProtoSender' and
        # their corresponding sessions not to recreate them all
        # the time since it's a (somewhat expensive) process.
        self._cached_clients = {}
        self._updates_thread = None
        self._phone_code_hashes = {}

    # endregion

    # region Connecting

    def connect(self, *args):
        """Connects to the Telegram servers, executing authentication if
           required. Note that authenticating to the Telegram servers is
           not the same as authenticating the desired user itself, which
           may require a call (or several) to 'sign_in' for the first time.

           *args will be ignored.
        """
        return super(TelegramClient, self).connect()

    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        self._set_updates_thread(running=False)
        super(TelegramClient, self).disconnect()

        # Also disconnect all the cached senders
        for sender in self._cached_clients.values():
            sender.disconnect()

        self._cached_clients.clear()

    # endregion

    # region Working with different connections

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
            export_auth = self.invoke(ExportAuthorizationRequest(dc_id))

            # Create a temporary session for this IP address, which needs
            # to be different because each auth_key is unique per DC.
            session = JsonSession(None)
            session.server_address = dc.ip_address
            session.port = dc.port
            client = TelegramBareClient(session, self.api_id, self.api_hash)
            client.connect(exported_auth=export_auth)

            if not bypass_cache:
                # Don't go through this expensive process every time.
                self._cached_clients[dc_id] = client
            return client

    def create_new_connection(self, on_dc=None):
        """Creates a new connection which can be used in parallel
           with the original TelegramClient. A TelegramBareClient
           will be returned already connected, and the caller is
           responsible to disconnect it.

           If 'on_dc' is None, the new client will run on the same
           data center as the current client (most common case).

           If the client is meant to be used on a different data
           center, the data center ID should be specified instead.

           Note that TelegramBareClients will not handle automatic
           reconnection (i.e. switching to another data center to
           download media), and InvalidDCError will be raised in
           such case.
        """
        if on_dc is None:
            client = TelegramBareClient(self.session, self.api_id, self.api_hash,
                                        proxy=self.proxy)
            client.connect()
        else:
            client = self._get_exported_client(on_dc, bypass_cache=True)

        return client

    # endregion

    # region Telegram requests functions

    def invoke(self, request, timeout=timedelta(seconds=5), *args):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           An optional timeout can be specified to cancel the operation if no
           result is received within such time, or None to disable any timeout.

           *args will be ignored.
        """
        if not issubclass(type(request), MTProtoRequest):
            raise ValueError('You can only invoke MtProtoRequests')

        if not self.sender:
            raise ValueError('You must be connected to invoke requests!')

        if self._updates_thread_receiving.is_set():
            self.sender.cancel_receive()

        try:
            self._lock.acquire()

            updates = [] if self._update_handlers else None
            result = super(TelegramClient, self).invoke(
                request, timeout=timeout, updates=updates)

            if updates:
                for update in updates:
                    for handler in self._update_handlers:
                        handler(update)

            # TODO Retry if 'result' is None?
            return result

        except (PhoneMigrateError, NetworkMigrateError, UserMigrateError) as e:
            self._logger.info('DC error when invoking request, '
                              'attempting to reconnect at DC {}'
                              .format(e.new_dc))

            self.reconnect(new_dc=e.new_dc)
            return self.invoke(request, timeout=timeout)

        finally:
            self._lock.release()

    def invoke_on_dc(self, request, dc_id,
                     timeout=timedelta(seconds=5), reconnect=False):
        """Invokes the given request on a different DC
           by making use of the exported MtProtoSenders.

           If 'reconnect=True', then the a reconnection will be performed and
           ConnectionResetError will be raised if it occurs a second time.
        """
        try:
            client = self._get_exported_client(
                dc_id, init_connection=reconnect)

            return client.invoke(request)

        except ConnectionResetError:
            if reconnect:
                raise
            else:
                return self.invoke_on_dc(request, dc_id,
                                         timeout=timeout, reconnect=True)

    # region Authorization requests

    def is_user_authorized(self):
        """Has the user been authorized yet
           (code request sent and confirmed)?"""
        return self.session and self.get_me() is not None

    def send_code_request(self, phone_number):
        """Sends a code request to the specified phone number"""
        result = self.invoke(
            SendCodeRequest(phone_number, self.api_id, self.api_hash))

        self._phone_code_hashes[phone_number] = result.phone_code_hash

    def sign_in(self, phone_number=None, code=None,
                password=None, bot_token=None):
        """Completes the sign in process with the phone number + code pair.

           If no phone or code is provided, then the sole password will be used.
           The password should be used after a normal authorization attempt
           has happened and an RPCError with `.password_required = True` was
           raised.

           To login as a bot, only `bot_token` should be provided.
           This should equal to the bot access hash provided by
           https://t.me/BotFather during your bot creation.

           If the login succeeds, the logged in user is returned.
        """
        if phone_number and code:
            if phone_number not in self._phone_code_hashes:
                raise ValueError(
                    'Please make sure to call send_code_request first.')

            try:
                result = self.invoke(SignInRequest(
                    phone_number, self._phone_code_hashes[phone_number], code))

            except (PhoneCodeEmptyError, PhoneCodeExpiredError,
                    PhoneCodeHashEmptyError, PhoneCodeInvalidError):
                return None

        elif password:
            salt = self.invoke(GetPasswordRequest()).current_salt
            result = self.invoke(
                CheckPasswordRequest(utils.get_password_hash(password, salt)))

        elif bot_token:
            result = self.invoke(ImportBotAuthorizationRequest(
                flags=0, bot_auth_token=bot_token,
                api_id=self.api_id, api_hash=self.api_hash))

        else:
            raise ValueError(
                'You must provide a phone_number and a code the first time, '
                'and a password only if an RPCError was raised before.')

        return result.user

    def sign_up(self, phone_number, code, first_name, last_name=''):
        """Signs up to Telegram. Make sure you sent a code request first!"""
        result = self.invoke(
            SignUpRequest(
                phone_number=phone_number,
                phone_code_hash=self._phone_code_hashes[phone_number],
                phone_code=code,
                first_name=first_name,
                last_name=last_name))

        self.session.user = result.user
        self.session.save()

    def log_out(self):
        """Logs out and deletes the current session.
           Returns True if everything went okay."""

        # Special flag when logging out (so the ack request confirms it)
        self.sender.logging_out = True
        try:
            self.invoke(LogOutRequest())
            self.disconnect()
            if not self.session.delete():
                return False

            self.session = None
            return True
        except (RPCError, ConnectionError):
            # Something happened when logging out, restore the state back
            self.sender.logging_out = False
            return False

    def get_me(self):
        """Gets "me" (the self user) which is currently authenticated,
           or None if the request fails (hence, not authenticated)."""
        try:
            return self.invoke(GetUsersRequest([InputUserSelf()]))[0]
        except UnauthorizedError:
            return None

    # endregion

    # region Dialogs ("chats") requests

    def get_dialogs(self,
                    limit=10,
                    offset_date=None,
                    offset_id=0,
                    offset_peer=InputPeerEmpty()):
        """Returns a tuple of lists ([dialogs], [entities])
           with at least 'limit' items each.

           If `limit` is 0, all dialogs will (should) retrieved.
           The `entities` represent the user, chat or channel
           corresponding to that dialog.
        """

        r = self.invoke(
            GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=limit))
        return (
            r.dialogs,
            [find_user_or_chat(d.peer, r.users, r.chats) for d in r.dialogs])

    # endregion

    # region Message requests

    def send_message(self,
                     entity,
                     message,
                     no_web_page=False):
        """Sends a message to the given entity (or input peer)
           and returns the sent message ID"""
        request = SendMessageRequest(
            peer=get_input_peer(entity),
            message=message,
            entities=[],
            no_webpage=no_web_page
        )
        self.invoke(request)
        return request.random_id

    def get_message_history(self,
                            entity,
                            limit=20,
                            offset_date=None,
                            offset_id=0,
                            max_id=0,
                            min_id=0,
                            add_offset=0):
        """
        Gets the message history for the specified entity

        :param entity:      The entity (or input peer) from whom to retrieve the message history
        :param limit:       Number of messages to be retrieved
        :param offset_date: Offset date (messages *previous* to this date will be retrieved)
        :param offset_id:   Offset message ID (only messages *previous* to the given ID will be retrieved)
        :param max_id:      All the messages with a higher (newer) ID or equal to this will be excluded
        :param min_id:      All the messages with a lower (older) ID or equal to this will be excluded
        :param add_offset:  Additional message offset (all of the specified offsets + this offset = older messages)

        :return: A tuple containing total message count and two more lists ([messages], [senders]).
                 Note that the sender can be null if it was not found!
        """
        result = self.invoke(
            GetHistoryRequest(
                get_input_peer(entity),
                limit=limit,
                offset_date=offset_date,
                offset_id=offset_id,
                max_id=max_id,
                min_id=min_id,
                add_offset=add_offset))

        # The result may be a messages slice (not all messages were retrieved)
        # or simply a messages TLObject. In the later case, no "count"
        # attribute is specified, so the total messages count is simply
        # the count of retrieved messages
        total_messages = getattr(result, 'count', len(result.messages))

        # Iterate over all the messages and find the sender User
        entities = [find_user_or_chat(m.from_id, result.users, result.chats)
                    if m.from_id is not None else
                    find_user_or_chat(m.to_id, result.users, result.chats)
                    for m in result.messages]

        return total_messages, result.messages, entities

    def send_read_acknowledge(self, entity, messages=None, max_id=None):
        """Sends a "read acknowledge" (i.e., notifying the given peer that we've
           read their messages, also known as the "double check").

           Either a list of messages (or a single message) can be given,
           or the maximum message ID (until which message we want to send the read acknowledge).

           Returns an AffectedMessages TLObject"""
        if max_id is None:
            if not messages:
                raise InvalidParameterError(
                    'Either a message list or a max_id must be provided.')

            if isinstance(messages, list):
                max_id = max(msg.id for msg in messages)
            else:
                max_id = messages.id

        return self.invoke(ReadHistoryRequest(peer=get_input_peer(entity), max_id=max_id))

    # endregion

    # region Uploading files

    def send_photo_file(self, input_file, entity, caption=''):
        """Sends a previously uploaded input_file
           (which should be a photo) to the given entity (or input peer)"""
        self.send_media_file(
            InputMediaUploadedPhoto(input_file, caption), entity)

    def send_document_file(self, input_file, entity, caption=''):
        """Sends a previously uploaded input_file
           (which should be a document) to the given entity (or input peer)"""

        # Determine mime-type and attributes
        # Take the first element by using [0] since it returns a tuple
        mime_type = guess_type(input_file.name)[0]
        attributes = [
            DocumentAttributeFilename(input_file.name)
            # TODO If the input file is an audio, find out:
            # Performer and song title and add DocumentAttributeAudio
        ]
        # Ensure we have a mime type, any; but it cannot be None
        # 'The "octet-stream" subtype is used to indicate that a body
        # contains arbitrary binary data.'
        if not mime_type:
            mime_type = 'application/octet-stream'
        self.send_media_file(
            InputMediaUploadedDocument(
                file=input_file,
                mime_type=mime_type,
                attributes=attributes,
                caption=caption),
            entity)

    def send_media_file(self, input_media, entity):
        """Sends any input_media (contact, document, photo...) to the given entity"""
        self.invoke(SendMediaRequest(
            peer=get_input_peer(entity),
            media=input_media
        ))

    # endregion

    # region Downloading media requests

    def download_profile_photo(self,
                               profile_photo,
                               file_path,
                               add_extension=True,
                               download_big=True):
        """Downloads the profile photo for an user or a chat (including channels).
           Returns False if no photo was provided, or if it was Empty"""

        if (not profile_photo or
                isinstance(profile_photo, UserProfilePhotoEmpty) or
                isinstance(profile_photo, ChatPhotoEmpty)):
            return False

        if add_extension:
            file_path += get_extension(profile_photo)

        if download_big:
            photo_location = profile_photo.photo_big
        else:
            photo_location = profile_photo.photo_small

        # Download the media with the largest size input file location
        self.download_file(
            InputFileLocation(
                volume_id=photo_location.volume_id,
                local_id=photo_location.local_id,
                secret=photo_location.secret
            ),
            file_path
        )
        return True

    def download_msg_media(self,
                           message_media,
                           file_path,
                           add_extension=True,
                           progress_callback=None):
        """Downloads the given MessageMedia (Photo, Document or Contact)
           into the desired file_path, optionally finding its extension automatically
           The progress_callback should be a callback function which takes two parameters,
           uploaded size (in bytes) and total file size (in bytes).
           This will be called every time a part is downloaded"""
        if type(message_media) == MessageMediaPhoto:
            return self.download_photo(message_media, file_path, add_extension,
                                       progress_callback)

        elif type(message_media) == MessageMediaDocument:
            return self.download_document(message_media, file_path,
                                          add_extension, progress_callback)

        elif type(message_media) == MessageMediaContact:
            return self.download_contact(message_media, file_path,
                                         add_extension)

    def download_photo(self,
                       message_media_photo,
                       file_path,
                       add_extension=False,
                       progress_callback=None):
        """Downloads MessageMediaPhoto's largest size into the desired
           file_path, optionally finding its extension automatically
           The progress_callback should be a callback function which takes two parameters,
           uploaded size (in bytes) and total file size (in bytes).
           This will be called every time a part is downloaded"""

        # Determine the photo and its largest size
        photo = message_media_photo.photo
        largest_size = photo.sizes[-1]
        file_size = largest_size.size
        largest_size = largest_size.location

        if add_extension:
            file_path += get_extension(message_media_photo)

        # Download the media with the largest size input file location
        self.download_file(
            InputFileLocation(
                volume_id=largest_size.volume_id,
                local_id=largest_size.local_id,
                secret=largest_size.secret
            ),
            file_path,
            file_size=file_size,
            progress_callback=progress_callback
        )
        return file_path

    def download_document(self,
                          message_media_document,
                          file_path=None,
                          add_extension=True,
                          progress_callback=None):
        """Downloads the given MessageMediaDocument into the desired
           file_path, optionally finding its extension automatically.
           If no file_path is given, it will try to be guessed from the document
           The progress_callback should be a callback function which takes two parameters,
           uploaded size (in bytes) and total file size (in bytes).
           This will be called every time a part is downloaded"""
        document = message_media_document.document
        file_size = document.size

        # If no file path was given, try to guess it from the attributes
        if file_path is None:
            for attr in document.attributes:
                if type(attr) == DocumentAttributeFilename:
                    file_path = attr.file_name
                    break  # This attribute has higher preference

                elif type(attr) == DocumentAttributeAudio:
                    file_path = '{} - {}'.format(attr.performer, attr.title)

            if file_path is None:
                raise ValueError('Could not infer a file_path for the document'
                                 '. Please provide a valid file_path manually')

        if add_extension:
            file_path += get_extension(message_media_document)

        self.download_file(
            InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                version=document.version
            ),
            file_path,
            file_size=file_size,
            progress_callback=progress_callback
        )
        return file_path

    @staticmethod
    def download_contact(message_media_contact, file_path, add_extension=True):
        """Downloads a media contact using the vCard 4.0 format"""

        first_name = message_media_contact.first_name
        last_name = message_media_contact.last_name
        phone_number = message_media_contact.phone_number

        # The only way we can save a contact in an understandable
        # way by phones is by using the .vCard format
        if add_extension:
            file_path += '.vcard'

        # Ensure that we'll be able to download the contact
        utils.ensure_parent_dir_exists(file_path)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write('BEGIN:VCARD\n')
            file.write('VERSION:4.0\n')
            file.write('N:{};{};;;\n'.format(first_name, last_name
                                             if last_name else ''))
            file.write('FN:{}\n'.format(' '.join((first_name, last_name))))
            file.write('TEL;TYPE=cell;VALUE=uri:tel:+{}\n'.format(
                phone_number))
            file.write('END:VCARD\n')

        return file_path

    def download_file(self,
                      input_location,
                      file,
                      part_size_kb=None,
                      file_size=None,
                      progress_callback=None,
                      on_dc=None):
        """Downloads the given InputFileLocation to file (a stream or str).

           If 'progress_callback' is not None, it should be a function that
           takes two parameters, (bytes_downloaded, total_bytes). Note that
           'total_bytes' simply equals 'file_size', and may be None.
        """
        if on_dc is None:
            try:
                super(TelegramClient, self).download_file(
                    input_location,
                    file,
                    part_size_kb=part_size_kb,
                    file_size=file_size,
                    progress_callback=progress_callback
                )
            except FileMigrateError as e:
                on_dc = e.new_dc

        if on_dc is not None:
            client = self._get_exported_client(on_dc)
            client.download_file(
                input_location,
                file,
                part_size_kb=part_size_kb,
                file_size=file_size,
                progress_callback=progress_callback
            )

    # endregion

    # endregion

    # region Updates handling

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        if not self.sender:
            raise RuntimeError("You can't add update handlers until you've "
                               "successfully connected to the server.")

        first_handler = not self._update_handlers
        self._update_handlers.append(handler)
        if first_handler:
            self._set_updates_thread(running=True)

    def remove_update_handler(self, handler):
        self._update_handlers.remove(handler)
        if not self._update_handlers:
            self._set_updates_thread(running=False)

    def list_update_handlers(self):
        return self._update_handlers[:]

    def _set_updates_thread(self, running):
        """Sets the updates thread status (running or not)"""
        if running == self._updates_thread_running.is_set():
            return

        # Different state, update the saved value and behave as required
        self._logger.info('Changing updates thread running status to %s', running)
        if running:
            self._updates_thread_running.set()
            if not self._updates_thread:
                self._updates_thread = Thread(
                    name='UpdatesThread', daemon=True,
                    target=self._updates_thread_method)

            self._updates_thread.start()
        else:
            self._updates_thread_running.clear()
            if self._updates_thread_receiving.is_set():
                self.sender.cancel_receive()

    def _updates_thread_method(self):
        """This method will run until specified and listen for incoming updates"""

        # Set a reasonable timeout when checking for updates
        timeout = timedelta(minutes=1)

        while self._updates_thread_running.is_set():
            # Always sleep a bit before each iteration to relax the CPU,
            # since it's possible to early 'continue' the loop to reach
            # the next iteration, but we still should to sleep.
            sleep(0.1)

            with self._lock:
                self._logger.debug('Updates thread acquired the lock')
                try:
                    self._updates_thread_receiving.set()
                    self._logger.debug(
                        'Trying to receive updates from the updates thread'
                    )

                    updates = self.sender.receive_updates(timeout=timeout)

                    self._updates_thread_receiving.clear()
                    self._logger.info(
                        'Received {} update(s) from the updates thread'
                        .format(len(updates))
                    )
                    for update in updates:
                        for handler in self._update_handlers:
                            handler(update)

                except ConnectionResetError:
                    self._logger.info('Server disconnected us. Reconnecting...')
                    self.reconnect()

                except TimeoutError:
                    self._logger.debug('Receiving updates timed out')

                except ReadCancelledError:
                    self._logger.info('Receiving updates cancelled')

                except BrokenPipeError:
                    self._logger.info('Tcp session is broken. Reconnecting...')
                    self.reconnect()

                except InvalidChecksumError:
                    self._logger.info('MTProto session is broken. Reconnecting...')
                    self.reconnect()

                except OSError:
                    self._logger.warning('OSError on updates thread, %s logging out',
                                         'was' if self.sender.logging_out else 'was not')

                    if self.sender.logging_out:
                        # This error is okay when logging out, means we got disconnected
                        # TODO Not sure why this happens because we call disconnect()...
                        self._set_updates_thread(running=False)
                    else:
                        raise

            self._logger.debug('Updates thread released the lock')

        # Thread is over, so clean unset its variable
        self._updates_thread = None

    # endregion
