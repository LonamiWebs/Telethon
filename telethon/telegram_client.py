import itertools
import os
import time
from collections import OrderedDict, UserList
from datetime import datetime, timedelta
from mimetypes import guess_type

try:
    import socks
except ImportError:
    socks = None

from . import TelegramBareClient
from . import helpers, utils
from .errors import (
    RPCError, UnauthorizedError, PhoneCodeEmptyError, PhoneCodeExpiredError,
    PhoneCodeHashEmptyError, PhoneCodeInvalidError, LocationInvalidError
)
from .network import ConnectionMode
from .tl import TLObject
from .tl.custom import Draft, Dialog
from .tl.functions.account import (
    GetPasswordRequest
)
from .tl.functions.auth import (
    CheckPasswordRequest, LogOutRequest, SendCodeRequest, SignInRequest,
    SignUpRequest, ResendCodeRequest, ImportBotAuthorizationRequest
)
from .tl.functions.contacts import (
    GetContactsRequest, ResolveUsernameRequest
)
from .tl.functions.messages import (
    GetDialogsRequest, GetHistoryRequest, SendMediaRequest,
    SendMessageRequest, GetChatsRequest, GetAllDraftsRequest,
    CheckChatInviteRequest
)

from .tl.functions import channels
from .tl.functions import messages

from .tl.functions.users import (
    GetUsersRequest
)
from .tl.functions.channels import (
    GetChannelsRequest, GetFullChannelRequest
)
from .tl.types import (
    DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    Message, MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    InputUserSelf, UserProfilePhoto, ChatPhoto, UpdateMessageID,
    UpdateNewChannelMessage, UpdateNewMessage, UpdateShortSentMessage,
    PeerUser, InputPeerUser, InputPeerChat, InputPeerChannel, MessageEmpty,
    ChatInvite, ChatInviteAlready, PeerChannel, Photo
)
from .tl.types.messages import DialogsSlice
from .extensions import markdown


class TelegramClient(TelegramBareClient):
    """Full featured TelegramClient meant to extend the basic functionality -

       As opposed to the TelegramBareClient, this one  features downloading
       media from different data centers, starting a second thread to
       handle updates, and some very common functionality.
    """

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 connection_mode=ConnectionMode.TCP_FULL,
                 use_ipv6=False,
                 proxy=None,
                 update_workers=None,
                 timeout=timedelta(seconds=5),
                 spawn_read_thread=True,
                 **kwargs):
        """Initializes the Telegram client with the specified API ID and Hash.

           Session can either be a `str` object (filename for the .session)
           or it can be a `Session` instance (in which case list_sessions()
           would probably not work). Pass 'None' for it to be a temporary
           session - remember to '.log_out()'!

           The 'connection_mode' should be any value under ConnectionMode.
           This will only affect how messages are sent over the network
           and how much processing is required before sending them.

           The integer 'update_workers' represents depending on its value:
             is None: Updates will *not* be stored in memory.
             = 0: Another thread is responsible for calling self.updates.poll()
             > 0: 'update_workers' background threads will be spawned, any
                  any of them will invoke all the self.updates.handlers.

           If 'spawn_read_thread', a background thread will be started once
           an authorized user has been logged in to Telegram to read items
           (such as updates and responses) from the network as soon as they
           occur, which will speed things up.

           If you don't want to spawn any additional threads, pending updates
           will be read and processed accordingly after invoking a request
           and not immediately. This is useful if you don't care about updates
           at all and have set 'update_workers=None'.

           If more named arguments are provided as **kwargs, they will be
           used to update the Session instance. Most common settings are:
             device_model     = platform.node()
             system_version   = platform.system()
             app_version      = TelegramClient.__version__
             lang_code        = 'en'
             system_lang_code = lang_code
             report_errors    = True
        """
        super().__init__(
            session, api_id, api_hash,
            connection_mode=connection_mode,
            use_ipv6=use_ipv6,
            proxy=proxy,
            update_workers=update_workers,
            spawn_read_thread=spawn_read_thread,
            timeout=timeout,
            **kwargs
        )

        # Some fields to easy signing in
        self._phone_code_hash = None
        self._phone = None

    # endregion

    # region Telegram requests functions

    # region Authorization requests

    def send_code_request(self, phone, force_sms=False):
        """Sends a code request to the specified phone number.

        :param str | int phone:
            The phone to which the code will be sent.
        :param bool force_sms:
            Whether to force sending as SMS.
        :return auth.SentCode:
            Information about the result of the request.
        """
        phone = utils.parse_phone(phone) or self._phone

        if not self._phone_code_hash:
            result = self(SendCodeRequest(phone, self.api_id, self.api_hash))
            self._phone_code_hash = result.phone_code_hash
        else:
            force_sms = True

        self._phone = phone

        if force_sms:
            result = self(ResendCodeRequest(phone, self._phone_code_hash))
            self._phone_code_hash = result.phone_code_hash

        return result

    def sign_in(self, phone=None, code=None,
                password=None, bot_token=None, phone_code_hash=None):
        """
        Starts or completes the sign in process with the given phone number
        or code that Telegram sent.

        :param str | int phone:
            The phone to send the code to if no code was provided, or to
            override the phone that was previously used with these requests.
        :param str | int code:
            The code that Telegram sent.
        :param str password:
            2FA password, should be used if a previous call raised
            SessionPasswordNeededError.
        :param str bot_token:
            Used to sign in as a bot. Not all requests will be available.
            This should be the hash the @BotFather gave you.
        :param str phone_code_hash:
            The hash returned by .send_code_request. This can be set to None
            to use the last hash known.

        :return auth.SentCode | User:
            The signed in user, or the information about .send_code_request().
        """

        if phone and not code:
            return self.send_code_request(phone)
        elif code:
            phone = utils.parse_phone(phone) or self._phone
            phone_code_hash = phone_code_hash or self._phone_code_hash
            if not phone:
                raise ValueError(
                    'Please make sure to call send_code_request first.'
                )
            if not phone_code_hash:
                raise ValueError('You also need to provide a phone_code_hash.')

            try:
                if isinstance(code, int):
                    code = str(code)

                result = self(SignInRequest(phone, phone_code_hash, code))

            except (PhoneCodeEmptyError, PhoneCodeExpiredError,
                    PhoneCodeHashEmptyError, PhoneCodeInvalidError):
                return None
        elif password:
            salt = self(GetPasswordRequest()).current_salt
            result = self(CheckPasswordRequest(
                helpers.get_password_hash(password, salt)
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
        """
        Signs up to Telegram if you don't have an account yet.
        You must call .send_code_request(phone) first.

        :param str | int code: The code sent by Telegram
        :param str first_name: The first name to be used by the new account.
        :param str last_name: Optional last name.
        :return User: The new created user.
        """
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
        """Logs out Telegram and deletes the current *.session file.

        :return bool: True if the operation was successful.
        """
        try:
            self(LogOutRequest())
        except RPCError:
            return False

        self.disconnect()
        self.session.delete()
        self.session = None
        return True

    def get_me(self):
        """
        Gets "me" (the self user) which is currently authenticated,
        or None if the request fails (hence, not authenticated).

        :return User: Your own user.
        """
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
        """
        Gets N "dialogs" (open "chats" or conversations with other people).

        :param limit:
            How many dialogs to be retrieved as maximum. Can be set to None
            to retrieve all dialogs. Note that this may take whole minutes
            if you have hundreds of dialogs, as Telegram will tell the library
            to slow down through a FloodWaitError.
        :param offset_date:
            The offset date to be used.
        :param offset_id:
            The message ID to be used as an offset.
        :param offset_peer:
            The peer to be used as an offset.

        :return UserList[telethon.tl.custom.Dialog]:
            A list dialogs, with an additional .total attribute on the list.
        """
        limit = float('inf') if limit is None else int(limit)
        if limit == 0:
            # Special case, get a single dialog and determine count
            dialogs = self(GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=1
            ))
            result = UserList()
            result.total = getattr(dialogs, 'count', len(dialogs.dialogs))
            return result

        total_count = 0
        dialogs = OrderedDict()  # Use peer id as identifier to avoid dupes
        while len(dialogs) < limit:
            real_limit = min(limit - len(dialogs), 100)
            r = self(GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=real_limit
            ))

            total_count = getattr(r, 'count', len(r.dialogs))
            messages = {m.id: m for m in r.messages}
            entities = {utils.get_peer_id(x, add_mark=True): x
                        for x in itertools.chain(r.users, r.chats)}

            for d in r.dialogs:
                dialogs[utils.get_peer_id(d.peer, add_mark=True)] = \
                    Dialog(self, d, entities, messages)

            if len(r.dialogs) < real_limit or not isinstance(r, DialogsSlice):
                # Less than we requested means we reached the end, or
                # we didn't get a DialogsSlice which means we got all.
                break

            offset_date = r.messages[-1].date
            offset_peer = utils.find_user_or_chat(
                r.dialogs[-1].peer, entities, entities
            )
            offset_id = r.messages[-1].id & 4294967296  # Telegram/danog magic

        dialogs = UserList(dialogs.values())
        dialogs.total = total_count
        return dialogs[:limit] if limit < float('inf') else dialogs

    def get_drafts(self):  # TODO: Ability to provide a `filter`
        """
        Gets all open draft messages.

        Returns a list of custom `Draft` objects that are easy to work with:
          You can call `draft.set_message('text')` to change the message,
          or delete it through `draft.delete()`.

        :return List[telethon.tl.custom.Draft]: A list of open drafts
        """
        response = self(GetAllDraftsRequest())
        self.session.process_entities(response)
        self.session.generate_sequence(response.seq)
        drafts = [Draft._from_update(self, u) for u in response.updates]
        return drafts

    def send_message(self,
                     entity,
                     message,
                     reply_to=None,
                     parse_mode=None,
                     link_preview=True):
        """
        Sends the given message to the specified entity (user/chat/channel).

        :param str | int | User | Chat | Channel entity:
            To who will it be sent.
        :param str message:
            The message to be sent.
        :param int | Message reply_to:
            Whether to reply to a message or not.
        :param str parse_mode:
            Can be 'md' or 'markdown' for markdown-like parsing, in a similar
            fashion how official clients work.
        :param link_preview:
            Should the link preview be shown?

        :return Message: the sent message
        """
        entity = self.get_input_entity(entity)
        if parse_mode:
            parse_mode = parse_mode.lower()
            if parse_mode in {'md', 'markdown'}:
                message, msg_entities = markdown.parse(message)
            else:
                raise ValueError('Unknown parsing mode: {}'.format(parse_mode))
        else:
            msg_entities = []

        request = SendMessageRequest(
            peer=entity,
            message=message,
            entities=msg_entities,
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
            if isinstance(update, (UpdateNewChannelMessage, UpdateNewMessage)):
                if update.message.id == msg_id:
                    return update.message

        return None  # Should not happen

    def delete_messages(self, entity, message_ids, revoke=True):
        """
        Deletes a message from a chat, optionally "for everyone" with argument
        `revoke` set to `True`.

        The `revoke` argument has no effect for Channels and Megagroups,
        where it inherently behaves as being `True`.

        Note: The `entity` argument can be `None` for normal chats, but it's
        mandatory to delete messages from Channels and Megagroups. It is also
        possible to supply a chat_id which will be automatically resolved to
        the right type of InputPeer.

        :param entity: ID or Entity of the chat
        :param list message_ids: ID(s) or `Message` object(s) of the message(s) to delete
        :param revoke: Delete the message for everyone or just this client
        :returns .messages.AffectedMessages: Messages affected by deletion.
        """

        if not isinstance(message_ids, list):
            message_ids = [message_ids]
        message_ids = [m.id if isinstance(m, Message) else int(m) for m in message_ids]

        if entity is None:
            return self(messages.DeleteMessagesRequest(message_ids, revoke=revoke))

        entity = self.get_input_entity(entity)

        if isinstance(entity, InputPeerChannel):
            return self(channels.DeleteMessagesRequest(entity, message_ids))
        else:
            return self(messages.DeleteMessagesRequest(message_ids, revoke=revoke))

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

        :param entity:
            The entity from whom to retrieve the message history.
        :param limit:
            Number of messages to be retrieved. Due to limitations with the API
            retrieving more than 3000 messages will take longer than half a
            minute (or even more based on previous calls). The limit may also
            be None, which would eventually return the whole history.
        :param offset_date:
            Offset date (messages *previous* to this date will be retrieved).
        :param offset_id:
            Offset message ID (only messages *previous* to the given ID will
            be retrieved).
        :param max_id:
            All the messages with a higher (newer) ID or equal to this will
            be excluded
        :param min_id:
            All the messages with a lower (older) ID or equal to this will
            be excluded.
        :param add_offset:
            Additional message offset
            (all of the specified offsets + this offset = older messages).

        :return: A list of messages with extra attributes:
                    .total = (on the list) total amount of messages sent
                    .sender = entity of the sender
                    .fwd_from.sender = if fwd_from, who sent it originally
                    .fwd_from.channel = if fwd_from, original channel
                    .to = entity to which the message was sent
        """
        entity = self.get_input_entity(entity)
        limit = float('inf') if limit is None else int(limit)
        if limit == 0:
            # No messages, but we still need to know the total message count
            result = self(GetHistoryRequest(
                peer=entity, limit=1,
                offset_date=None, offset_id=0, max_id=0, min_id=0, add_offset=0
            ))
            return getattr(result, 'count', len(result.messages)), [], []

        total_messages = 0
        messages = UserList()
        entities = {}
        while len(messages) < limit:
            # Telegram has a hard limit of 100
            real_limit = min(limit - len(messages), 100)
            result = self(GetHistoryRequest(
                peer=entity,
                limit=real_limit,
                offset_date=offset_date,
                offset_id=offset_id,
                max_id=max_id,
                min_id=min_id,
                add_offset=add_offset
            ))
            messages.extend(
                m for m in result.messages if not isinstance(m, MessageEmpty)
            )
            total_messages = getattr(result, 'count', len(result.messages))

            # TODO We can potentially use self.session.database, but since
            # it might be disabled, use a local dictionary.
            for u in result.users:
                entities[utils.get_peer_id(u, add_mark=True)] = u
            for c in result.chats:
                entities[utils.get_peer_id(c, add_mark=True)] = c

            if len(result.messages) < real_limit:
                break

            offset_id = result.messages[-1].id
            offset_date = result.messages[-1].date

            # Telegram limit seems to be 3000 messages within 30 seconds in
            # batches of 100 messages each request (since the FloodWait was
            # of 30 seconds). If the limit is greater than that, we will
            # sleep 1s between each request.
            if limit > 3000:
                time.sleep(1)

        # Add a few extra attributes to the Message to make it friendlier.
        messages.total = total_messages
        for m in messages:
            # TODO Better way to return a total without tuples?
            m.sender = (None if not m.from_id else
                        entities[utils.get_peer_id(m.from_id, add_mark=True)])

            if getattr(m, 'fwd_from', None):
                m.fwd_from.sender = (
                    None if not m.fwd_from.from_id else
                    entities[utils.get_peer_id(
                        m.fwd_from.from_id, add_mark=True
                    )]
                )
                m.fwd_from.channel = (
                    None if not m.fwd_from.channel_id else
                    entities[utils.get_peer_id(
                        PeerChannel(m.fwd_from.channel_id), add_mark=True
                    )]
                )

            m.to = entities[utils.get_peer_id(m.to_id, add_mark=True)]

        return messages

    def send_read_acknowledge(self, entity, message=None, max_id=None):
        """
        Sends a "read acknowledge" (i.e., notifying the given peer that we've
        read their messages, also known as the "double check").

        :param entity: The chat where these messages are located.
        :param message: Either a list of messages or a single message.
        :param max_id: Overrides messages, until which message should the
                       acknowledge should be sent.
        :return:
        """
        if max_id is None:
            if not messages:
                raise ValueError(
                    'Either a message list or a max_id must be provided.')

            if hasattr(message, '__iter__'):
                max_id = max(msg.id for msg in message)
            else:
                max_id = message.id

        entity = self.get_input_entity(entity)
        if entity == InputPeerChannel:
            return self(channels.ReadHistoryRequest(entity, max_id=max_id))
        else:
            return self(messages.ReadHistoryRequest(entity, max_id=max_id))

    @staticmethod
    def _get_reply_to(reply_to):
        """Sanitizes the 'reply_to' parameter a user may send"""
        if reply_to is None:
            return None

        if isinstance(reply_to, int):
            return reply_to

        if isinstance(reply_to, TLObject) and \
                        type(reply_to).SUBCLASS_OF_ID == 0x790009e3:
            # hex(crc32(b'Message')) = 0x790009e3
            return reply_to.id

        raise TypeError('Invalid reply_to type: {}'.format(type(reply_to)))

    # endregion

    # region Uploading files

    def send_file(self, entity, file, caption='',
                  force_document=False, progress_callback=None,
                  reply_to=None,
                  attributes=None,
                  **kwargs):
        """
        Sends a file to the specified entity.

        :param entity:
            Who will receive the file.
        :param file:
            The path of the file, byte array, or stream that will be sent.
            Note that if a byte array or a stream is given, a filename
            or its type won't be inferred, and it will be sent as an
            "unnamed application/octet-stream".

            Subsequent calls with the very same file will result in
            immediate uploads, unless .clear_file_cache() is called.
        :param caption:
            Optional caption for the sent media message.
        :param force_document:
            If left to False and the file is a path that ends with .png, .jpg
            and such, the file will be sent as a photo. Otherwise always as
            a document.
        :param progress_callback:
            A callback function accepting two parameters: (sent bytes, total)
        :param reply_to:
            Same as reply_to from .send_message().
        :param attributes:
            Optional attributes that override the inferred ones, like
            DocumentAttributeFilename and so on.
        :param kwargs:
           If "is_voice_note" in kwargs, despite its value, and the file is
           sent as a document, it will be sent as a voice note.
        :return:
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
                attr_dict = {
                    DocumentAttributeFilename:
                    DocumentAttributeFilename(os.path.basename(file))
                    # TODO If the input file is an audio, find out:
                    # Performer and song title and add DocumentAttributeAudio
                }
            else:
                attr_dict = {
                    DocumentAttributeFilename:
                    DocumentAttributeFilename('unnamed')
                }

            if 'is_voice_note' in kwargs:
                attr_dict[DocumentAttributeAudio] = \
                    DocumentAttributeAudio(0, voice=True)

            # Now override the attributes if any. As we have a dict of
            # {cls: instance}, we can override any class with the list
            # of attributes provided by the user easily.
            if attributes:
                for a in attributes:
                    attr_dict[type(a)] = a

            # Ensure we have a mime type, any; but it cannot be None
            # 'The "octet-stream" subtype is used to indicate that a body
            # contains arbitrary binary data.'
            if not mime_type:
                mime_type = 'application/octet-stream'

            media = InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type,
                attributes=list(attr_dict.values()),
                caption=caption
            )

        # Once the media type is properly specified and the file uploaded,
        # send the media message to the desired entity.
        self(SendMediaRequest(
            peer=self.get_input_entity(entity),
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
        """
        Downloads the profile photo of the given entity (user/chat/channel).

        :param entity:
            From who the photo will be downloaded.
        :param file:
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.
        :param download_big:
            Whether to use the big version of the available photos.
        :return:
            None if no photo was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
        """
        photo = entity
        possible_names = []
        if not isinstance(entity, TLObject) or type(entity).SUBCLASS_OF_ID in (
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

            photo = entity.photo

        if not isinstance(photo, UserProfilePhoto) and \
                not isinstance(photo, ChatPhoto):
            return None

        photo_location = photo.photo_big if download_big else photo.photo_small
        file = self._get_proper_filename(
            file, 'profile_photo', '.jpg',
            possible_names=possible_names
        )

        # Download the media with the largest size input file location
        try:
            self.download_file(
                InputFileLocation(
                    volume_id=photo_location.volume_id,
                    local_id=photo_location.local_id,
                    secret=photo_location.secret
                ),
                file
            )
        except LocationInvalidError:
            # See issue #500, Android app fails as of v4.6.0 (1155).
            # The fix seems to be using the full channel chat photo.
            ie = self.get_input_entity(entity)
            if isinstance(ie, InputPeerChannel):
                full = self(GetFullChannelRequest(ie))
                return self._download_photo(
                    full.full_chat.chat_photo, file,
                    date=None, progress_callback=None
                )
            else:
                # Until there's a report for chats, no need to.
                return None
        return file

    def download_media(self, message, file=None, progress_callback=None):
        """
        Downloads the given media, or the media from a specified Message.
        :param message:
            The media or message containing the media that will be downloaded.
        :param file:
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.
        :param progress_callback:
            A callback function accepting two parameters: (recv bytes, total)
        :return:
        """
        # TODO This won't work for messageService
        if isinstance(message, Message):
            date = message.date
            media = message.media
        else:
            date = datetime.now()
            media = message

        if isinstance(media, (MessageMediaPhoto, Photo)):
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

    def _download_photo(self, photo, file, date, progress_callback):
        """Specialized version of .download_media() for photos"""

        # Determine the photo and its largest size
        if isinstance(photo, MessageMediaPhoto):
            photo = photo.photo
        if not isinstance(photo, Photo):
            return

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
            file, 'document', utils.get_extension(mm_doc),
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
            # Remove these pesky characters
            first_name = first_name.replace(';', '')
            last_name = (last_name or '').replace(';', '')
            f.write('BEGIN:VCARD\n')
            f.write('VERSION:4.0\n')
            f.write('N:{};{};;;\n'.format(first_name, last_name))
            f.write('FN:{} {}\n'.format(first_name, last_name))
            f.write('TEL;TYPE=cell;VALUE=uri:tel:+{}\n'.format(phone_number))
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
                if not date:
                    date = datetime.now()
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

    def get_entity(self, entity):
        """
        Turns the given entity into a valid Telegram user or chat.

        :param entity:
            The entity (or iterable of entities) to be transformed.
            If it's a string which can be converted to an integer or starts
            with '+' it will be resolved as if it were a phone number.

            If it doesn't start with '+' or starts with a '@' it will be
            be resolved from the username. If no exact match is returned,
            an error will be raised.

            If the entity is an integer or a Peer, its information will be
            returned through a call to self.get_input_peer(entity).

            If the entity is neither, and it's not a TLObject, an
            error will be raised.

        :return: User, Chat or Channel corresponding to the input entity.
        """
        if not isinstance(entity, str) and hasattr(entity, '__iter__'):
            single = False
        else:
            single = True
            entity = (entity,)

        # Group input entities by string (resolve username),
        # input users (get users), input chat (get chats) and
        # input channels (get channels) to get the most entities
        # in the less amount of calls possible.
        inputs = [
            x if isinstance(x, str) else self.get_input_entity(x)
            for x in entity
        ]
        users = [x for x in inputs if isinstance(x, InputPeerUser)]
        chats = [x.chat_id for x in inputs if isinstance(x, InputPeerChat)]
        channels = [x for x in inputs if isinstance(x, InputPeerChannel)]
        if users:
            # GetUsersRequest has a limit of 200 per call
            tmp = []
            while users:
                curr, users = users[:200], users[200:]
                tmp.extend(self(GetUsersRequest(curr)))
            users = tmp
        if chats:  # TODO Handle chats slice?
            chats = self(GetChatsRequest(chats)).chats
        if channels:
            channels = self(GetChannelsRequest(channels)).chats

        # Merge users, chats and channels into a single dictionary
        id_entity = {
            utils.get_peer_id(x, add_mark=True): x
            for x in itertools.chain(users, chats, channels)
        }

        # We could check saved usernames and put them into the users,
        # chats and channels list from before. While this would reduce
        # the amount of ResolveUsername calls, it would fail to catch
        # username changes.
        result = [
            self._get_entity_from_string(x) if isinstance(x, str)
            else id_entity[utils.get_peer_id(x, add_mark=True)]
            for x in inputs
        ]
        return result[0] if single else result

    def _get_entity_from_string(self, string):
        """
        Gets a full entity from the given string, which may be a phone or
        an username, and processes all the found entities on the session.
        The string may also be a user link, or a channel/chat invite link.

        This method has the side effect of adding the found users to the
        session database, so it can be queried later without API calls,
        if this option is enabled on the session.

        Returns the found entity, or raises TypeError if not found.
        """
        phone = utils.parse_phone(string)
        if phone:
            for user in self(GetContactsRequest(0)).users:
                if user.phone == phone:
                    return user
        else:
            string, is_join_chat = utils.parse_username(string)
            if is_join_chat:
                invite = self(CheckChatInviteRequest(string))
                if isinstance(invite, ChatInvite):
                    # If it's an invite to a chat, the user must join before
                    # for the link to be resolved and work, otherwise raise.
                    if invite.channel:
                        return invite.channel
                elif isinstance(invite, ChatInviteAlready):
                    return invite.chat
            else:
                result = self(ResolveUsernameRequest(string))
                for entity in itertools.chain(result.users, result.chats):
                    if entity.username.lower() == string:
                        return entity

        raise TypeError(
            'Cannot turn "{}" into any entity (user or chat)'.format(string)
        )

    def get_input_entity(self, peer):
        """
        Turns the given peer into its input entity version. Most requests
        use this kind of InputUser, InputChat and so on, so this is the
        most suitable call to make for those cases.

        :param peer:
            The integer ID of an user or otherwise either of a
            PeerUser, PeerChat or PeerChannel, for which to get its
            Input* version.

            If this Peer hasn't been seen before by the library, the top
            dialogs will be loaded and their entities saved to the session
            file (unless this feature was disabled explicitly).

            If in the end the access hash required for the peer was not found,
            a ValueError will be raised.

        :return: InputPeerUser, InputPeerChat or InputPeerChannel.
        """
        try:
            # First try to get the entity from cache, otherwise figure it out
            return self.session.get_input_entity(peer)
        except ValueError:
            pass

        if isinstance(peer, str):
            return utils.get_input_peer(self._get_entity_from_string(peer))

        is_peer = False
        if isinstance(peer, int):
            peer = PeerUser(peer)
            is_peer = True

        elif isinstance(peer, TLObject):
            is_peer = type(peer).SUBCLASS_OF_ID == 0x2d45687  # crc32(b'Peer')
            if not is_peer:
                try:
                    return utils.get_input_peer(peer)
                except TypeError:
                    pass

        if not is_peer:
            raise TypeError(
                'Cannot turn "{}" into an input entity.'.format(peer)
            )

        # Not found, look in the latest dialogs.
        # This is useful if for instance someone just sent a message but
        # the updates didn't specify who, as this person or chat should
        # be in the latest dialogs.
        dialogs = self(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=0,
            exclude_pinned=True
        ))

        target = utils.get_peer_id(peer, add_mark=True)
        for entity in itertools.chain(dialogs.users, dialogs.chats):
            if utils.get_peer_id(entity, add_mark=True) == target:
                return utils.get_input_peer(entity)

        raise TypeError(
            'Could not find the input entity corresponding to "{}".'
            'Make sure you have encountered this peer before.'.format(peer)
        )

    # endregion
