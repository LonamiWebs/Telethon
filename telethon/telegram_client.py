import os
import threading
from datetime import datetime, timedelta
from functools import lru_cache
from mimetypes import guess_type
from threading import Thread
from time import sleep

try:
    import socks
except ImportError:
    socks = None

from . import TelegramBareClient
from . import helpers as utils
from .errors import (
    RPCError, UnauthorizedError, InvalidParameterError, PhoneCodeEmptyError,
    PhoneMigrateError, NetworkMigrateError, UserMigrateError,
    PhoneCodeExpiredError, PhoneCodeHashEmptyError, PhoneCodeInvalidError
)
from .network import ConnectionMode
from .tl import Session, TLObject
from .tl.functions import PingRequest
from .tl.functions.account import (
    GetPasswordRequest
)
from .tl.functions.auth import (
    CheckPasswordRequest, LogOutRequest, SendCodeRequest, SignInRequest,
    SignUpRequest, ImportBotAuthorizationRequest
)
from .tl.functions.contacts import (
    GetContactsRequest, ResolveUsernameRequest
)
from .tl.functions.messages import (
    GetDialogsRequest, GetHistoryRequest, ReadHistoryRequest, SendMediaRequest,
    SendMessageRequest
)
from .tl.functions.updates import (
    GetStateRequest
)
from .tl.functions.users import (
    GetUsersRequest
)
from .tl.types import (
    DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    Message, MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    InputUserSelf, UserProfilePhoto, ChatPhoto, UpdateMessageID,
    UpdateNewMessage, UpdateShortSentMessage
)
from .utils import find_user_or_chat, get_extension


class TelegramClient(TelegramBareClient):
    """Full featured TelegramClient meant to extend the basic functionality -

       As opposed to the TelegramBareClient, this one  features downloading
       media from different data centers, starting a second thread to
       handle updates, and some very common functionality.
    """

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 connection_mode=ConnectionMode.TCP_FULL,
                 proxy=None,
                 process_updates=False,
                 timeout=timedelta(seconds=5),
                 **kwargs):
        """Initializes the Telegram client with the specified API ID and Hash.

           Session can either be a `str` object (filename for the .session)
           or it can be a `Session` instance (in which case list_sessions()
           would probably not work). Pass 'None' for it to be a temporary
           session - remember to '.log_out()'!

           The 'connection_mode' should be any value under ConnectionMode.
           This will only affect how messages are sent over the network
           and how much processing is required before sending them.

           If 'process_updates' is set to True, incoming updates will be
           processed and you must manually call 'self.updates.poll()' from
           another thread to retrieve the saved update objects, or your
           memory will fill with these. You may modify the value of
           'self.updates.polling' at any later point.

           Despite the value of 'process_updates', if you later call
           '.add_update_handler(...)', updates will also be processed
           and the update objects will be passed to the handlers you added.

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

        super().__init__(
            session, api_id, api_hash,
            connection_mode=connection_mode,
            proxy=proxy,
            process_updates=process_updates,
            timeout=timeout
        )

        # Used on connection - the user may modify these and reconnect
        kwargs['app_version'] = kwargs.get('app_version', self.__version__)
        for name, value in kwargs.items():
            if hasattr(self.session, name):
                setattr(self.session, name, value)

        self._updates_thread = None
        self._phone_code_hash = None
        self._phone = None

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

           exported_auth is meant for internal purposes and can be ignored.
        """
        if socks and self._recv_thread:
            # Treat proxy errors specially since they're not related to
            # Telegram itself, but rather to the proxy. If any happens on
            # the read thread forward it to the main thread.
            try:
                ok = super().connect(exported_auth=exported_auth)
            except socks.ProxyConnectionError as e:
                ok = False
                # Report the exception to the main thread
                self.updates.set_error(e)
        else:
            ok = super().connect(exported_auth=exported_auth)

        if not ok:
            return False

        self._user_connected = True
        try:
            self.sync_updates()
            self._set_connected_and_authorized()
        except UnauthorizedError:
            self._authorized = False

        return True

    def disconnect(self):
        """Disconnects from the Telegram server
           and stops all the spawned threads"""
        self._user_connected = False
        self._recv_thread = None

        # This will trigger a "ConnectionResetError", usually, the background
        # thread would try restarting the connection but since the
        # ._recv_thread = None, it knows it doesn't have to.
        super().disconnect()

        # Also disconnect all the cached senders
        for sender in self._cached_clients.values():
            sender.disconnect()

        self._cached_clients.clear()

    # endregion

    # region Working with different connections

    def _on_read_thread(self):
        return self._recv_thread is not None and \
               threading.get_ident() == self._recv_thread.ident

    def create_new_connection(self, on_dc=None, timeout=timedelta(seconds=5)):
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
                self.session, self.api_id, self.api_hash,
                proxy=self._sender.connection.conn.proxy, timeout=timeout
            )
            client.connect()
        else:
            client = self._get_exported_client(on_dc, bypass_cache=True)

        return client

    # endregion

    # region Telegram requests functions

    def invoke(self, *requests, **kwargs):
        """Invokes (sends) one or several MTProtoRequest and returns
           (receives) their result. An optional named 'retries' parameter
           can be used, indicating how many times it should retry.
        """
        # This is only valid when the read thread is reconnecting,
        # that is, the connection lock is locked.
        if self._on_read_thread() and not self._connect_lock.locked():
            return  # Just ignore, we would be raising and crashing the thread

        self.updates.check_error()

        try:
            # We should call receive from this thread if there's no background
            # thread reading or if the server disconnected us and we're trying
            # to reconnect. This is because the read thread may either be
            # locked also trying to reconnect or we may be said thread already.
            call_receive = \
                self._recv_thread is None or self._connect_lock.locked()

            return super().invoke(
                *requests,
                call_receive=call_receive,
                retries=kwargs.get('retries', 5)
            )

        except (PhoneMigrateError, NetworkMigrateError, UserMigrateError) as e:
            self._logger.debug('DC error when invoking request, '
                               'attempting to reconnect at DC {}'
                               .format(e.new_dc))

            # TODO What happens with the background thread here?
            # For normal use cases, this won't happen, because this will only
            # be on the very first connection (not authorized, not running),
            # but may be an issue for people who actually travel?
            self._reconnect(new_dc=e.new_dc)
            return self.invoke(*requests)

        except ConnectionResetError as e:
            if self._connect_lock.locked():
                # We are connecting and we don't want to reconnect there...
                raise
            while self._user_connected and not self._reconnect():
                sleep(0.1)  # Retry forever until we can send the request

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
        return self._authorized

    def send_code_request(self, phone):
        """Sends a code request to the specified phone number"""
        if isinstance(phone, int):
            phone = str(phone)
        elif phone.startswith('+'):
            phone = phone.strip('+')

        result = self(SendCodeRequest(phone, self.api_id, self.api_hash))
        self._phone = phone
        self._phone_code_hash = result.phone_code_hash
        return result

    def sign_in(self, phone=None, code=None,
                password=None, bot_token=None):
        """Completes the sign in process with the phone number + code pair.

           If no phone or code is provided, then the sole password will be used.
           The password should be used after a normal authorization attempt
           has happened and an SessionPasswordNeededError was raised.

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
            result = self(CheckPasswordRequest(
                utils.get_password_hash(password, salt)
            ))
        elif bot_token:
            result = self(ImportBotAuthorizationRequest(
                flags=0, bot_auth_token=bot_token,
                api_id=self.api_id, api_hash=self.api_hash
            ))
        else:
            raise ValueError(
                'You must provide a phone and a code the first time, '
                'and a password only if an RPCError was raised before.'
            )

        self._set_connected_and_authorized()
        return result.user

    def sign_up(self, code, first_name, last_name=''):
        """Signs up to Telegram. Make sure you sent a code request first!"""
        result = self(SignUpRequest(
            phone_number=self._phone,
            phone_code_hash=self._phone_code_hash,
            phone_code=code,
            first_name=first_name,
            last_name=last_name
        ))

        self._set_connected_and_authorized()
        return result.user

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
                     reply_to=None,
                     link_preview=True):
        """Sends a message to the given entity (or input peer)
           and returns the sent message as a Telegram object.

           If 'reply_to' is set to either a message or a message ID,
           the sent message will be replying to such message.
        """
        entity = self.get_entity(entity)
        request = SendMessageRequest(
            peer=entity,
            message=message,
            entities=[],
            no_webpage=not link_preview,
            reply_to_msg_id=self._get_reply_to(reply_to)
        )
        result = self(request)
        if isinstance(result, UpdateShortSentMessage):
            return Message(
                id=result.id,
                to_id=entity,
                message=message,
                date=result.date,
                out=result.out,
                media=result.media,
                entities=result.entities
            )

        # Telegram seems to send updateMessageID first, then updateNewMessage,
        # however let's not rely on that just in case.
        msg_id = None
        for update in result.updates:
            if isinstance(update, UpdateMessageID):
                if update.random_id == request.random_id:
                    msg_id = update.id
                    break

        for update in result.updates:
            if isinstance(update, UpdateNewMessage):
                if update.message.id == msg_id:
                    return update.message

        return None  # Should not happen

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
            peer=self.get_entity(entity),
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
            peer=self.get_entity(entity),
            max_id=max_id
        ))

    @staticmethod
    def _get_reply_to(reply_to):
        """Sanitizes the 'reply_to' parameter a user may send"""
        if reply_to is None:
            return None

        if isinstance(reply_to, int):
            return reply_to

        if isinstance(reply_to, TLObject) and \
                type(reply_to).subclass_of_id == 0x790009e3:
            # hex(crc32(b'Message')) = 0x790009e3
            return reply_to.id

        raise ValueError('Invalid reply_to type: ', type(reply_to))

    # endregion

    # region Uploading files

    def send_file(self, entity, file, caption='',
                  force_document=False, progress_callback=None,
                  reply_to=None,
                  **kwargs):
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

           The "reply_to" parameter works exactly as the one on .send_message.

           If "is_voice_note" in kwargs, despite its value, and the file is
           sent as a document, it will be sent as a voice note.

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

            if 'is_voice_note' in kwargs:
                attributes.append(DocumentAttributeAudio(0, voice=True))

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
            peer=self.get_entity(entity),
            media=media,
            reply_to_msg_id=self._get_reply_to(reply_to)
        ))

    def send_voice_note(self, entity, file, caption='', upload_progress=None,
                        reply_to=None):
        """Wrapper method around .send_file() with is_voice_note=()"""
        return self.send_file(entity, file, caption,
                              upload_progress=upload_progress,
                              reply_to=reply_to,
                              is_voice_note=())  # empty tuple is enough

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
            entity = self.get_entity(entity)
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

    @lru_cache()
    def get_entity(self, entity):
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
                contacts = self(GetContactsRequest(0))
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
            self._recv_thread = Thread(
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
