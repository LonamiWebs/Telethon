import platform
from datetime import datetime, timedelta
from hashlib import md5
from mimetypes import guess_type
from os import listdir, path

# Import some externalized utilities to work with the Telegram types and more
import telethon.helpers as utils
import telethon.network.authenticator as authenticator
from telethon.errors import *
from telethon.network import MtProtoSender, TcpTransport
from telethon.parser.markdown_parser import parse_message_entities
# For sending and receiving requests
from telethon.tl import MTProtoRequest, Session
from telethon.tl.all_tlobjects import layer
from telethon.tl.functions import InitConnectionRequest, InvokeWithLayerRequest
# The following is required to get the password salt
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.functions.auth import (CheckPasswordRequest, LogOutRequest,
                                        SendCodeRequest, SignInRequest,
                                        SignUpRequest)
from telethon.tl.functions.auth import ImportBotAuthorizationRequest
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.messages import (
    GetDialogsRequest, GetHistoryRequest, ReadHistoryRequest, SendMediaRequest,
    SendMessageRequest)
# The Requests and types that we'll be using
from telethon.tl.functions.upload import (
    GetFileRequest, SaveBigFilePartRequest, SaveFilePartRequest)
# All the types we need to work with
from telethon.tl.types import (
    ChatPhotoEmpty, DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFile, InputFileBig, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    UserProfilePhotoEmpty)
from telethon.utils import (find_user_or_chat, get_input_peer,
                            get_appropiate_part_size, get_extension)


class TelegramClient:

    # Current TelegramClient version
    __version__ = '0.8'

    # region Default methods of class

    def __init__(self, session, api_id, api_hash, proxy=None):
        """Initializes the Telegram client with the specified API ID and Hash.

           Session can either be a `str` object (the filename for the loaded/saved .session)
           or it can be a `Session` instance (in which case list_sessions() would probably not work).
           If you don't want any file to be saved, pass `None`

           In the later case, you are free to override the `Session` class to provide different
           .save() and .load() implementations to suit your needs."""

        if api_id is None or api_hash is None:
            raise PermissionError(
                'Your API ID or Hash are invalid. Please read "Requirements" on README.rst')

        self.api_id = api_id
        self.api_hash = api_hash

        # Determine what session object we have
        if isinstance(session, str):
            self.session = Session.try_load_or_create_new(session)
        elif isinstance(session, Session):
            self.session = session
        else:
            raise ValueError(
                'The given session must either be a string or a Session instance.')

        self.transport = None
        self.proxy = proxy  # Will be used when a TcpTransport is created

        # These will be set later
        self.dc_options = None
        self.sender = None
        self.phone_code_hashes = {}

        # We need to be signed in before we can listen for updates
        self.signed_in = False

    def __del__(self):
        """Releases the Telegram client, performing disconnection."""
        self.disconnect()

    # endregion

    # region Connecting

    def connect(self, reconnect=False):
        """Connects to the Telegram servers, executing authentication if required.
           Note that authenticating to the Telegram servers is not the same as authenticating
           the app, which requires to send a code first."""
        if self.transport is None:
            self.transport = TcpTransport(self.session.server_address,
                                          self.session.port, proxy=self.proxy)

        try:
            if not self.session.auth_key or (reconnect and self.sender is not None):
                self.session.auth_key, self.session.time_offset = \
                    authenticator.do_authentication(self.transport)

                self.session.save()

            self.sender = MtProtoSender(self.transport, self.session)

            # Now it's time to send an InitConnectionRequest
            # This must always be invoked with the layer we'll be using
            query = InitConnectionRequest(
                api_id=self.api_id,
                device_model=platform.node(),
                system_version=platform.system(),
                app_version=self.__version__,
                lang_code='en',
                query=GetConfigRequest())

            result = self.invoke(
                InvokeWithLayerRequest(
                    layer=layer, query=query))

            # We're only interested in the DC options,
            # although many other options are available!
            self.dc_options = result.dc_options

            # We're signed in if we're authorized
            self.signed_in = self.is_user_authorized()
            return True
        except RPCError as error:
            print('Could not stabilise initial connection: {}'.format(error))
            return False

    def reconnect_to_dc(self, dc_id):
        """Reconnects to the specified DC ID. This is automatically called after an InvalidDCError is raised"""
        if self.dc_options is None or not self.dc_options:
            raise ConnectionError(
                "Can't reconnect. Stabilise an initial connection first.")

        dc = next(dc for dc in self.dc_options if dc.id == dc_id)

        self.transport.close()
        self.transport = None
        self.session.server_address = dc.ip_address
        self.session.port = dc.port
        self.session.save()

        self.connect(reconnect=True)

    def disconnect(self):
        """Disconnects from the Telegram server **and pauses all the spawned threads**"""
        if self.sender:
            self.sender.disconnect()
            self.sender = None
        if self.transport:
            self.transport.close()
            self.transport = None

    # endregion

    # region Telegram requests functions

    def invoke(self, request, timeout=timedelta(seconds=5), throw_invalid_dc=False):
        """Invokes a MTProtoRequest (sends and receives it) and returns its result.
           An optional timeout can be given to cancel the operation after the time delta.
           Timeout can be set to None for no timeout.

           If throw_invalid_dc is True, these errors won't be caught (useful to
           avoid infinite recursion). This should not be set to True manually."""
        if not issubclass(type(request), MTProtoRequest):
            raise ValueError('You can only invoke MtProtoRequests')

        if not self.sender:
            raise ValueError('You must be connected to invoke requests!')

        try:
            self.sender.send(request)
            self.sender.receive(request, timeout)

            return request.result

        except InvalidDCError as error:
            if throw_invalid_dc:
                raise error

            self.reconnect_to_dc(error.new_dc)
            return self.invoke(request, timeout=timeout, throw_invalid_dc=True)

    # region Authorization requests

    def is_user_authorized(self):
        """Has the user been authorized yet (code request sent and confirmed)?
           Note that this will NOT yield the correct result if the session was revoked by another client!"""
        return self.session.user is not None

    def send_code_request(self, phone_number):
        """Sends a code request to the specified phone number"""
        result = self.invoke(SendCodeRequest(phone_number, self.api_id, self.api_hash))
        self.phone_code_hashes[phone_number] = result.phone_code_hash

    def sign_in(self, phone_number=None, code=None, password=None, bot_token=None):
        """Completes the authorization of a phone number by providing the received code.

           If no phone or code is provided, then the sole password will be used. The password
           should be used after a normal authorization attempt has happened and an RPCError
           with `.password_required = True` was raised.

           To login as a bot, only `bot_token` should be provided. This should equal to the
           bot access hash provided by https://t.me/BotFather during your bot creation."""
        if phone_number and code:
            if phone_number not in self.phone_code_hashes:
                raise ValueError(
                    'Please make sure you have called send_code_request first.')

            try:
                result = self.invoke(
                    SignInRequest(phone_number, self.phone_code_hashes[
                        phone_number], code))

            except RPCError as error:
                if error.message.startswith('PHONE_CODE_'):
                    print(error)
                    return False
                else:
                    raise error
        elif password:
            salt = self.invoke(GetPasswordRequest()).current_salt
            result = self.invoke(
                CheckPasswordRequest(utils.get_password_hash(password, salt)))
        elif bot_token:
            result = self.invoke(
                ImportBotAuthorizationRequest(flags=0,
                                              api_id=self.api_id,
                                              api_hash=self.api_hash,
                                              bot_auth_token=bot_token))
        else:
            raise ValueError(
                'You must provide a phone_number and a code for the first time, '
                'and a password only if an RPCError was raised before.')

        # Result is an Auth.Authorization TLObject
        self.session.user = result.user
        self.session.save()

        # Now that we're authorized, set the signed_in flag
        # to True so update handlers can be added
        self.signed_in = True
        return True

    def sign_up(self, phone_number, code, first_name, last_name=''):
        """Signs up to Telegram. Make sure you sent a code request first!"""
        result = self.invoke(
            SignUpRequest(
                phone_number=phone_number,
                phone_code_hash=self.phone_code_hashes[phone_number],
                phone_code=code,
                first_name=first_name,
                last_name=last_name))

        self.session.user = result.user
        self.session.save()

    def log_out(self):
        """Logs out and deletes the current session. Returns True if everything went OK"""
        # Special flag when logging out (so the ack request confirms it)
        self.sender.logging_out = True
        try:
            self.invoke(LogOutRequest())
            self.disconnect()
            if not self.session.delete():
                return False

            self.session = None
        except:
            # Something happened when logging out, restore the state back
            self.sender.logging_out = False
            return False

    @staticmethod
    def list_sessions():
        """Lists all the sessions of the users who have ever connected
           using this client and never logged out"""
        return [path.splitext(path.basename(f))[
            0]  # splitext = split ext (not spli text!)
                for f in listdir('.') if f.endswith('.session')]

    # endregion

    # region Dialogs ("chats") requests

    def get_dialogs(self,
                    limit=10,
                    offset_date=None,
                    offset_id=0,
                    offset_peer=InputPeerEmpty()):
        """Returns a tuple of lists ([dialogs], [entities]) with at least 'limit' items each.
           If `limit` is 0, all dialogs will be retrieved.
           The `entity` represents the user, chat or channel corresponding to that dialog"""

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
                     markdown=False,
                     no_web_page=False):
        """Sends a message to the given entity (or input peer) and returns the sent message ID"""
        if markdown:
            msg, entities = parse_message_entities(message)
        else:
            msg, entities = message, []

        msg_id = utils.generate_random_long()
        self.invoke(
            SendMessageRequest(
                peer=get_input_peer(entity),
                message=msg,
                random_id=msg_id,
                entities=entities,
                no_webpage=no_web_page))
        return msg_id

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

        # The result may be a messages slice (not all messages were retrieved) or
        # simply a messages TLObject. In the later case, no "count" attribute is specified:
        # the total messages count is retrieved by counting all the retrieved messages
        total_messages = getattr(result, 'count', len(result.messages))

        # Iterate over all the messages and find the sender User
        users = []
        for msg in result.messages:
            for usr in result.users:
                if msg.from_id == usr.id:
                    users.append(usr)
                    break

        return total_messages, result.messages, users

    def send_read_acknowledge(self, entity, messages=None, max_id=None):
        """Sends a "read acknowledge" (i.e., notifying the given peer that we've
           read their messages, also known as the "double check ✅✅").

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

    # TODO Handle media downloading/uploading in a different session?
    #  "It is recommended that large queries (upload.getFile, upload.saveFilePart)
    #   be handled through a separate session and a separate connection"
    # region Uploading media requests

    def upload_file(self,
                    file_path,
                    part_size_kb=None,
                    file_name=None,
                    progress_callback=None):
        """Uploads the specified file_path and returns a handle which can be later used

        :param file_path: The file path of the file that will be uploaded
        :param part_size_kb: The part size when uploading the file. None = Automatic
        :param file_name: The name of the uploaded file. None = Automatic
        :param progress_callback: A callback function which takes two parameters,
                                  uploaded size (in bytes) and total file size (in bytes)
                                  This is called every time a part is uploaded
        """
        file_size = path.getsize(file_path)
        if not part_size_kb:
            part_size_kb = get_appropiate_part_size(file_size)

        if part_size_kb > 512:
            raise ValueError('The part size must be less or equal to 512KB')

        part_size = int(part_size_kb * 1024)
        if part_size % 1024 != 0:
            raise ValueError('The part size must be evenly divisible by 1024')

        # Determine whether the file is too big (over 10MB) or not
        # Telegram does make a distinction between smaller or larger files
        is_large = file_size > 10 * 1024 * 1024
        part_count = (file_size + part_size - 1) // part_size

        # Multiply the datetime timestamp by 10^6 to get the ticks
        # This is high likely going to be unique
        file_id = utils.generate_random_long()
        hash_md5 = md5()

        with open(file_path, 'rb') as file:
            for part_index in range(part_count):
                # Read the file by in chunks of size part_size
                part = file.read(part_size)

                # The SavePartRequest is different depending on whether
                # the file is too large or not (over or less than 10MB)
                if is_large:
                    request = SaveBigFilePartRequest(file_id, part_index,
                                                     part_count, part)
                else:
                    request = SaveFilePartRequest(file_id, part_index, part)

                # Invoke the file upload and increment both the part index and MD5 checksum
                result = self.invoke(request)
                if result:
                    if not is_large:
                        # No need to update the hash if it's a large file
                        hash_md5.update(part)

                    if progress_callback:
                        progress_callback(file.tell(), file_size)
                else:
                    raise ValueError('Could not upload file part #{}'.format(
                        part_index))

        # Set a default file name if None was specified
        if not file_name:
            file_name = path.basename(file_path)

        # After the file has been uploaded, we can return a handle pointing to it
        if is_large:
            return InputFileBig(
                id=file_id,
                parts=part_count,
                name=file_name)
        else:
            return InputFile(
                id=file_id,
                parts=part_count,
                name=file_name,
                md5_checksum=hash_md5.hexdigest())

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
        # «The "octet-stream" subtype is used to indicate that a body contains arbitrary binary data.»
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
        """Sends any input_media (contact, document, photo...) to the given entiy"""
        self.invoke(
            SendMediaRequest(
                peer=get_input_peer(entity),
                media=input_media,
                random_id=utils.generate_random_long()))

    # endregion

    # region Downloading media requests

    def download_profile_photo(self,
                               profile_photo,
                               file_path,
                               add_extension=True,
                               download_big=True):
        """Downloads the profile photo for an user or a chat (including channels).
           Returns False if no photo was providen, or if it was Empty"""

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
        self.download_file_loc(
            InputFileLocation(
                volume_id=photo_location.volume_id,
                local_id=photo_location.local_id,
                secret=photo_location.secret),
            file_path)
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
        self.download_file_loc(
            InputFileLocation(
                volume_id=largest_size.volume_id,
                local_id=largest_size.local_id,
                secret=largest_size.secret),
            file_path,
            file_size=file_size,
            progress_callback=progress_callback)
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
                print('Could not determine a filename for the document')

        if add_extension:
            file_path += get_extension(message_media_document)

        self.download_file_loc(
            InputDocumentFileLocation(
                id=document.id,
                access_hash=document.access_hash,
                version=document.version),
            file_path,
            file_size=file_size,
            progress_callback=progress_callback)
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

    def download_file_loc(self,
                          input_location,
                          file_path,
                          part_size_kb=64,
                          file_size=None,
                          progress_callback=None):
        """Downloads media from the given input_file_location to the specified file_path.
           If a progress_callback function is given, it will be called taking two
           arguments (downloaded bytes count and total file size)"""

        if not part_size_kb:
            if not file_size:
                raise ValueError('A part size value must be provided')
            else:
                part_size_kb = get_appropiate_part_size(file_size)

        part_size = int(part_size_kb * 1024)
        if part_size % 1024 != 0:
            raise ValueError('The part size must be evenly divisible by 1024')

        # Ensure that we'll be able to download the media
        utils.ensure_parent_dir_exists(file_path)

        # Start with an offset index of 0
        offset_index = 0
        with open(file_path, 'wb') as file:
            while True:
                # The current offset equals the offset_index multiplied by the part size
                offset = offset_index * part_size
                result = self.invoke(
                    GetFileRequest(input_location, offset, part_size))
                offset_index += 1

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    return result.type  # Return some extra information

                file.write(result.bytes)
                if progress_callback:
                    progress_callback(file.tell(), file_size)

    # endregion

    # endregion

    # region Updates handling

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        if not self.signed_in:
            raise ValueError(
                "You cannot add update handlers until you've signed in.")

        self.sender.add_update_handler(handler)

    def remove_update_handler(self, handler):
        self.sender.remove_update_handler(handler)

    def list_update_handlers(self):
        return [ handler.__name__ for handler in self.sender.on_update_handlers ]

    # endregion
