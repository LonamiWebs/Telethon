import os
from datetime import datetime, timedelta
from mimetypes import guess_type
from threading import Event, RLock, Thread
from time import sleep, time

from . import TelegramBareClient

# Import some externalized utilities to work with the Telegram types and more
from . import helpers as utils
from .errors import (RPCError, UnauthorizedError, InvalidParameterError,
                     ReadCancelledError, PhoneCodeEmptyError,
                     PhoneMigrateError, NetworkMigrateError, UserMigrateError,
                     PhoneCodeExpiredError, PhoneCodeHashEmptyError,
                     PhoneCodeInvalidError, InvalidChecksumError)

# For sending and receiving requests
from .tl import Session, TLObject

# Required to get the password salt
from .tl.functions.account import GetPasswordRequest

# Logging in and out
from .tl.functions.auth import (CheckPasswordRequest, LogOutRequest,
                                SendCodeRequest, SignInRequest,
                                SignUpRequest, ImportBotAuthorizationRequest)

# Easier access to common methods
from .tl.functions.messages import (
    GetDialogsRequest, GetHistoryRequest, ReadHistoryRequest, SendMediaRequest,
    SendMessageRequest)

from .tl.functions.contacts import GetContactsRequest, ResolveUsernameRequest

# For .get_me() and ensuring we're authorized
from .tl.functions.users import GetUsersRequest

# So the server doesn't stop sending updates to us
from .tl.functions import PingRequest

# All the types we need to work with
from .tl.types import (
    DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    Message, MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    InputUserSelf, UserProfilePhoto, ChatPhoto)

from .utils import find_user_or_chat, get_extension


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
                 timeout=timedelta(seconds=5),
                 **kwargs):
        """Initializes the Telegram client with the specified API ID and Hash.

           Session can either be a `str` object (filename for the .session)
           or it can be a `Session` instance (in which case list_sessions()
           would probably not work). Pass 'None' for it to be a temporary
           session - remember to '.log_out()'!

           If more named arguments are provided as **kwargs, they will be
           used to update the Session instance. Most common settings are:
             device_model     = platform.node()
             system_version   = platform.system()
             app_version      = TelegramClient.__version__
             lang_code        = 'en'
             system_lang_code = lang_code
             report_errors    = True
        """
        if not api_id or not api_hash:
            raise PermissionError(
                "Your API ID or Hash cannot be empty or None. "
                "Refer to Telethon's README.rst for more information.")

        # Determine what session object we have
        if isinstance(session, str) or session is None:
            session = Session.try_load_or_create_new(session)
        elif not isinstance(session, Session):
            raise ValueError(
                'The given session must be a str or a Session instance.')

        super().__init__(session, api_id, api_hash, proxy, timeout=timeout)

        # Safety across multiple threads (for the updates thread)
        self._lock = RLock()

        # Updates-related members
        self._update_handlers = []
        self._updates_thread_running = Event()
        self._updates_thread_receiving = Event()

        self._next_ping_at = 0
        self.ping_interval = 60  # Seconds

        # Used on connection - the user may modify these and reconnect
        kwargs['app_version'] = kwargs.get('app_version', self.__version__)
        for name, value in kwargs.items():
            if hasattr(self.session, name):
                setattr(self.session, name, value)

        self._updates_thread = None
        self._phone_code_hash = None
        self._phone = None

        # Uploaded files cache so subsequent calls are instant
        self._upload_cache = {}

    # endregion

    # region Connecting

    def connect(self, *args):
        """Connects to the Telegram servers, executing authentication if
           required. Note that authenticating to the Telegram servers is
           not the same as authenticating the desired user itself, which
           may require a call (or several) to 'sign_in' for the first time.

           The specified timeout will be used on internal .invoke()'s.

           *args will be ignored.
        """
        result = super().connect()

        # Checking if there are update_handlers and if true, start running updates thread.
        # This situation may occur on reconnecting.
        if result and self._update_handlers:
            self._set_updates_thread(running=True)

        return result


    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        self._set_updates_thread(running=False)
        super().disconnect()

        # Also disconnect all the cached senders
        for sender in self._cached_clients.values():
            sender.disconnect()

        self._cached_clients.clear()

    # endregion

    # region Working with different connections

    def create_new_connection(self, on_dc=None):
        """Creates a new connection which can be used in parallel
           with the original TelegramClient. A TelegramBareClient
           will be returned already connected, and the caller is
           responsible to disconnect it.

           If 'on_dc' is None, the new client will run on the same
           data center as the current client (most common case).

           If the client is meant to be used on a different data
           center, the data center ID should be specified instead.
        """
        if on_dc is None:
            client = TelegramBareClient(
                self.session, self.api_id, self.api_hash, proxy=self.proxy)
            client.connect()
        else:
            client = self._get_exported_client(on_dc, bypass_cache=True)

        return client

    # endregion

    # region Telegram requests functions

    def invoke(self, request, *args):
        """Invokes (sends) a MTProtoRequest and returns (receives) its result.

           An optional timeout can be specified to cancel the operation if no
           result is received within such time, or None to disable any timeout.

           *args will be ignored.
        """
        if self._updates_thread_receiving.is_set():
            self._sender.cancel_receive()

        try:
            self._lock.acquire()

            updates = [] if self._update_handlers else None
            result = super().invoke(
                request, updates=updates
            )

            if updates:
                for update in updates:
                    for handler in self._update_handlers:
                        handler(update)

            # TODO Retry if 'result' is None?
            return result

        except (PhoneMigrateError, NetworkMigrateError, UserMigrateError) as e:
            self._logger.debug('DC error when invoking request, '
                              'attempting to reconnect at DC {}'
                              .format(e.new_dc))

            self.reconnect(new_dc=e.new_dc)
            return self.invoke(request)

        finally:
            self._lock.release()

    # Let people use client(SomeRequest()) instead client.invoke(...)
    __call__ = invoke

    def invoke_on_dc(self, request, dc_id, reconnect=False):
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
                return self.invoke_on_dc(request, dc_id, reconnect=True)

    # region Authorization requests

    def is_user_authorized(self):
        """Has the user been authorized yet
           (code request sent and confirmed)?"""
        return self.session and self.get_me() is not None

    def send_code_request(self, phone):
        """Sends a code request to the specified phone number"""
        result = self(
            SendCodeRequest(phone, self.api_id, self.api_hash))
        self._phone = phone
        self._phone_code_hash = result.phone_code_hash
        return result

    def sign_in(self, phone=None, code=None,
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

        if phone and not code:
            return self.send_code_request(phone)
        elif code:
            if self._phone is None:
                raise ValueError(
                    'Please make sure to call send_code_request first.')

            try:
                if isinstance(code, int):
                    code = str(code)
                result = self(SignInRequest(
                    self._phone, self._phone_code_hash, code
                ))

            except (PhoneCodeEmptyError, PhoneCodeExpiredError,
                    PhoneCodeHashEmptyError, PhoneCodeInvalidError):
                return None

        elif password:
            salt = self(GetPasswordRequest()).current_salt
            result = self(
                CheckPasswordRequest(utils.get_password_hash(password, salt)))

        elif bot_token:
            result = self(ImportBotAuthorizationRequest(
                flags=0, bot_auth_token=bot_token,
                api_id=self.api_id, api_hash=self.api_hash))

        else:
            raise ValueError(
                'You must provide a phone and a code the first time, '
                'and a password only if an RPCError was raised before.')

        return result.user

    def sign_up(self, code, first_name, last_name=''):
        """Signs up to Telegram. Make sure you sent a code request first!"""
        result = self(
            SignUpRequest(
                phone=self._phone,
                phone_code_hash=self._phone_code_hash,
                phone_code=code,
                first_name=first_name,
                last_name=last_name))

        self.session.user = result.user
        self.session.save()

    def log_out(self):
        """Logs out and deletes the current session.
           Returns True if everything went okay."""
        # Special flag when logging out (so the ack request confirms it)
        self._sender.logging_out = True

        try:
            self(LogOutRequest())
            # The server may have already disconnected us, we still
            # try to disconnect to make sure.
            self.disconnect()
        except (RPCError, ConnectionError):
            # Something happened when logging out, restore the state back
            self._sender.logging_out = False
            return False

        self.session.delete()
        self.session = None
        return True

    def get_me(self):
        """Gets "me" (the self user) which is currently authenticated,
           or None if the request fails (hence, not authenticated)."""
        try:
            return self(GetUsersRequest([InputUserSelf()]))[0]
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

        r = self(
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
                     link_preview=True):
        """Sends a message to the given entity (or input peer)
           and returns the sent message ID.

           The entity may be a phone or an username at the expense of
           some performance loss.
        """
        request = SendMessageRequest(
            peer=self._get_entity(entity),
            message=message,
            entities=[],
            no_webpage=not link_preview
        )
        result = self(request)
        for handler in self._update_handlers:
            handler(result)
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

        :param entity:      The entity from whom to retrieve the message history
        :param limit:       Number of messages to be retrieved
        :param offset_date: Offset date (messages *previous* to this date will be retrieved)
        :param offset_id:   Offset message ID (only messages *previous* to the given ID will be retrieved)
        :param max_id:      All the messages with a higher (newer) ID or equal to this will be excluded
        :param min_id:      All the messages with a lower (older) ID or equal to this will be excluded
        :param add_offset:  Additional message offset (all of the specified offsets + this offset = older messages)

        :return: A tuple containing total message count and two more lists ([messages], [senders]).
                 Note that the sender can be null if it was not found!

           The entity may be a phone or an username at the expense of
           some performance loss.
        """
        result = self(GetHistoryRequest(
            peer=self._get_entity(entity),
            limit=limit,
            offset_date=offset_date,
            offset_id=offset_id,
            max_id=max_id,
            min_id=min_id,
            add_offset=add_offset
        ))

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

           Returns an AffectedMessages TLObject

           The entity may be a phone or an username at the expense of
           some performance loss.
        """
        if max_id is None:
            if not messages:
                raise InvalidParameterError(
                    'Either a message list or a max_id must be provided.')

            if isinstance(messages, list):
                max_id = max(msg.id for msg in messages)
            else:
                max_id = messages.id

        return self(ReadHistoryRequest(
            peer=self._get_entity(entity),
            max_id=max_id
        ))

    # endregion

    # region Uploading files

    def send_file(self, entity, file, caption='',
                  force_document=False, progress_callback=None):
        """Sends a file to the specified entity.
           The file may either be a path, a byte array, or a stream.

           An optional caption can also be specified for said file.

           If "force_document" is False, the file will be sent as a photo
           if it's recognised to have a common image format (e.g. .png, .jpg).

           Otherwise, the file will always be sent as an uncompressed document.

           Subsequent calls with the very same file will result in
           immediate uploads, unless .clear_file_cache() is called.

           If "progress_callback" is not None, it should be a function that
           takes two parameters, (bytes_uploaded, total_bytes).

           The entity may be a phone or an username at the expense of
           some performance loss.
        """
        as_photo = False
        if isinstance(file, str):
            lowercase_file = file.lower()
            as_photo = any(
                lowercase_file.endswith(ext)
                for ext in ('.png', '.jpg', '.gif', '.jpeg')
            )

        file_hash = hash(file)
        if file_hash in self._upload_cache:
            file_handle = self._upload_cache[file_hash]
        else:
            self._upload_cache[file_hash] = file_handle = self.upload_file(
                file, progress_callback=progress_callback
            )

        if as_photo and not force_document:
            media = InputMediaUploadedPhoto(file_handle, caption)
        else:
            mime_type = None
            if isinstance(file, str):
                # Determine mime-type and attributes
                # Take the first element by using [0] since it returns a tuple
                mime_type = guess_type(file)[0]
                attributes = [
                    DocumentAttributeFilename(os.path.abspath(file))
                    # TODO If the input file is an audio, find out:
                    # Performer and song title and add DocumentAttributeAudio
                ]
            else:
                attributes = [DocumentAttributeFilename('unnamed')]

            # Ensure we have a mime type, any; but it cannot be None
            # 'The "octet-stream" subtype is used to indicate that a body
            # contains arbitrary binary data.'
            if not mime_type:
                mime_type = 'application/octet-stream'

            media = InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type,
                attributes=attributes,
                caption=caption
            )

        # Once the media type is properly specified and the file uploaded,
        # send the media message to the desired entity.
        self(SendMediaRequest(
            peer=self._get_entity(entity),
            media=media
        ))

    def clear_file_cache(self):
        """Calls to .send_file() will cache the remote location of the
           uploaded files so that subsequent files can be immediate, so
           uploading the same file path will result in using the cached
           version. To avoid this a call to this method should be made.
        """
        self._upload_cache.clear()

    # endregion

    # region Downloading media requests

    def download_profile_photo(self, entity, file=None, download_big=True):
        """Downloads the profile photo for an user or a chat (channels too).
           Returns None if no photo was provided, or if it was Empty.

           If an entity itself (an user, chat or channel) is given, the photo
           to be downloaded will be downloaded automatically.

           On success, the file path is returned since it may differ from
           the one provided.

           The specified output file can either be a file path, a directory,
           or a stream-like object. If the path exists and is a file, it will
           be overwritten.

           The entity may be a phone or an username at the expense of
           some performance loss.
        """
        possible_names = []
        if not isinstance(entity, TLObject) or type(entity).subclass_of_id in (
                    0x2da17977, 0xc5af5d94, 0x1f4661b9, 0xd49a2697
            ):
            # Maybe it is an user or a chat? Or their full versions?
            #
            # The hexadecimal numbers above are simply:
            # hex(crc32(x.encode('ascii'))) for x in
            # ('User', 'Chat', 'UserFull', 'ChatFull')
            entity = self._get_entity(entity)
            if not hasattr(entity, 'photo'):
                # Special case: may be a ChatFull with photo:Photo
                # This is different from a normal UserProfilePhoto and Chat
                if hasattr(entity, 'chat_photo'):
                    return self._download_photo(
                        entity.chat_photo, file,
                        date=None, progress_callback=None
                    )
                else:
                    # Give up
                    return None

            for attr in ('username', 'first_name', 'title'):
                possible_names.append(getattr(entity, attr, None))

            entity = entity.photo

        if not isinstance(entity, UserProfilePhoto) and \
                not isinstance(entity, ChatPhoto):
            return None

        if download_big:
            photo_location = entity.photo_big
        else:
            photo_location = entity.photo_small

        file = self._get_proper_filename(
            file, 'profile_photo', '.jpg',
            possible_names=possible_names
        )

        # Download the media with the largest size input file location
        self.download_file(
            InputFileLocation(
                volume_id=photo_location.volume_id,
                local_id=photo_location.local_id,
                secret=photo_location.secret
            ),
            file
        )
        return file

    def download_media(self, message, file=None, progress_callback=None):
        """Downloads the media from a specified Message (it can also be
           the message.media) into the desired file (a stream or str),
           optionally finding its extension automatically.

           The specified output file can either be a file path, a directory,
           or a stream-like object. If the path exists and is a file, it will
           be overwritten.

           If the operation succeeds, the path will be returned (since
           the extension may have been added automatically). Otherwise,
           None is returned.

           The progress_callback should be a callback function which takes
           two parameters, uploaded size and total file size (both in bytes).
           This will be called every time a part is downloaded
        """
        # TODO This won't work for messageService
        if isinstance(message, Message):
            date = message.date
            media = message.media
        else:
            date = datetime.now()
            media = message

        if isinstance(media, MessageMediaPhoto):
            return self._download_photo(
                media, file, date, progress_callback
            )
        elif isinstance(media, MessageMediaDocument):
            return self._download_document(
                media, file, date, progress_callback
            )
        elif isinstance(media, MessageMediaContact):
            return self._download_contact(
                media, file
            )

    def _download_photo(self, mm_photo, file, date, progress_callback):
        """Specialized version of .download_media() for photos"""

        # Determine the photo and its largest size
        photo = mm_photo.photo
        largest_size = photo.sizes[-1]
        file_size = largest_size.size
        largest_size = largest_size.location

        file = self._get_proper_filename(file, 'photo', '.jpg', date=date)

        # Download the media with the largest size input file location
        self.download_file(
            InputFileLocation(
                volume_id=largest_size.volume_id,
                local_id=largest_size.local_id,
                secret=largest_size.secret
            ),
            file,
            file_size=file_size,
            progress_callback=progress_callback
        )
        return file

    def _download_document(self, mm_doc, file, date, progress_callback):
        """Specialized version of .download_media() for documents"""
        document = mm_doc.document
        file_size = document.size

        possible_names = []
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                possible_names.insert(0, attr.file_name)

            elif isinstance(attr, DocumentAttributeAudio):
                possible_names.append('{} - {}'.format(
                    attr.performer, attr.title
                ))

        file = self._get_proper_filename(
            file, 'document', get_extension(mm_doc),
            date=date, possible_names=possible_names
        )

        self.download_file(
            InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                version=document.version
            ),
            file,
            file_size=file_size,
            progress_callback=progress_callback
        )
        return file

    @staticmethod
    def _download_contact(mm_contact, file):
        """Specialized version of .download_media() for contacts.
           Will make use of the vCard 4.0 format
        """
        first_name = mm_contact.first_name
        last_name = mm_contact.last_name
        phone_number = mm_contact.phone_number

        if isinstance(file, str):
            file = TelegramClient._get_proper_filename(
                file, 'contact', '.vcard',
                possible_names=[first_name, phone_number, last_name]
            )
            f = open(file, 'w', encoding='utf-8')
        else:
            f = file

        try:
            f.write('BEGIN:VCARD\n')
            f.write('VERSION:4.0\n')
            f.write('N:{};{};;;\n'.format(
                first_name, last_name if last_name else '')
            )
            f.write('FN:{}\n'.format(' '.join((first_name, last_name))))
            f.write('TEL;TYPE=cell;VALUE=uri:tel:+{}\n'.format(
                phone_number))
            f.write('END:VCARD\n')
        finally:
            # Only close the stream if we opened it
            if isinstance(file, str):
                f.close()

        return file

    @staticmethod
    def _get_proper_filename(file, kind, extension,
                             date=None, possible_names=None):
        """Gets a proper filename for 'file', if this is a path.

           'kind' should be the kind of the output file (photo, document...)
           'extension' should be the extension to be added to the file if
                       the filename doesn't have any yet
           'date' should be when this file was originally sent, if known
           'possible_names' should be an ordered list of possible names

           If no modification is made to the path, any existing file
           will be overwritten.
           If any modification is made to the path, this method will
           ensure that no existing file will be overwritten.
        """
        if file is not None and not isinstance(file, str):
            # Probably a stream-like object, we cannot set a filename here
            return file

        if file is None:
            file = ''
        elif os.path.isfile(file):
            # Make no modifications to valid existing paths
            return file

        if os.path.isdir(file) or not file:
            try:
                name = None if possible_names is None else next(
                    x for x in possible_names if x
                )
            except StopIteration:
                name = None

            if not name:
                name = '{}_{}-{:02}-{:02}_{:02}-{:02}-{:02}'.format(
                    kind,
                    date.year, date.month, date.day,
                    date.hour, date.minute, date.second,
                )
            file = os.path.join(file, name)

        directory, name = os.path.split(file)
        name, ext = os.path.splitext(name)
        if not ext:
            ext = extension

        result = os.path.join(directory, name + ext)
        if not os.path.isfile(result):
            return result

        i = 1
        while True:
            result = os.path.join(directory, '{} ({}){}'.format(name, i, ext))
            if not os.path.isfile(result):
                return result
            i += 1

    # endregion

    # endregion

    # region Small utilities to make users' life easier

    def _get_entity(self, entity):
        """Turns an entity into a valid Telegram user or chat.
           If "entity" is a string, and starts with '+', or if
           it is an integer value, it will be resolved as if it
           were a phone number.

           If "entity" is a string and doesn't start with '+', or
           it starts with '@', it will be resolved from the username.
           If no exact match is returned, an error will be raised.

           If the entity is neither, and it's not a TLObject, an
           error will be raised.
        """
        # TODO Maybe cache both the contacts and the entities.
        # If an user cannot be found, force a cache update through
        # a public method (since users may change their username)
        if isinstance(entity, TLObject):
            return entity

        if isinstance(entity, int):
            entity = '+{}'.format(entity)  # Turn it into a phone-like str

        if isinstance(entity, str):
            if entity.startswith('+'):
                contacts = self(GetContactsRequest(''))
                try:
                    stripped_phone = entity.strip('+')
                    return next(
                        u for u in contacts.users
                        if u.phone and u.phone.endswith(stripped_phone)
                    )
                except StopIteration:
                    raise ValueError(
                        'Could not find user with phone {}, '
                        'add them to your contacts first'.format(entity)
                    )
            else:
                username = entity.strip('@').lower()
                resolved = self(ResolveUsernameRequest(username))
                for c in resolved.chats:
                    if getattr(c, 'username', '').lower() == username:
                        return c
                for u in resolved.users:
                    if getattr(u, 'username', '').lower() == username:
                        return u

                raise ValueError(
                    'Could not find user with username {}'.format(entity)
                )

        raise ValueError(
            'Cannot turn "{}" into any entity (user or chat)'.format(entity)
        )

    # endregion

    # region Updates handling

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        if not self._sender:
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
        self._logger.debug('Changing updates thread running status to %s', running)
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
                self._sender.cancel_receive()

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

                    if time() > self._next_ping_at:
                        self._next_ping_at = time() + self.ping_interval
                        self(PingRequest(utils.generate_random_long()))

                    updates = self._sender.receive_updates(timeout=timeout)

                    self._updates_thread_receiving.clear()
                    self._logger.debug(
                        'Received {} update(s) from the updates thread'
                        .format(len(updates))
                    )
                    for update in updates:
                        for handler in self._update_handlers:
                            handler(update)

                except ConnectionResetError:
                    self._logger.debug('Server disconnected us. Reconnecting...')
                    self.reconnect()

                except TimeoutError:
                    self._logger.debug('Receiving updates timed out')

                except ReadCancelledError:
                    self._logger.debug('Receiving updates cancelled')

                except BrokenPipeError:
                    self._logger.debug('Tcp session is broken. Reconnecting...')
                    self.reconnect()

                except InvalidChecksumError:
                    self._logger.debug('MTProto session is broken. Reconnecting...')
                    self.reconnect()

                except OSError:
                    self._logger.debug('OSError on updates thread, %s logging out',
                                         'was' if self._sender.logging_out else 'was not')

                    if self._sender.logging_out:
                        # This error is okay when logging out, means we got disconnected
                        # TODO Not sure why this happens because we call disconnect()...
                        self._set_updates_thread(running=False)
                    else:
                        raise

            self._logger.debug('Updates thread released the lock')

        # Thread is over, so clean unset its variable
        self._updates_thread = None

    # endregion
