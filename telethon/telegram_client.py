import getpass
import hashlib
import io
import itertools
import logging
import os
import re
import sys
import time
import warnings
from collections import OrderedDict, UserList
from datetime import datetime, timedelta
from io import BytesIO
from mimetypes import guess_type

from .crypto import CdnDecrypter
from .tl.custom import InputSizedFile
from .tl.functions.upload import (
    SaveBigFilePartRequest, SaveFilePartRequest, GetFileRequest
)
from .tl.types.upload import FileCdnRedirect

try:
    import socks
except ImportError:
    socks = None

try:
    import hachoir
    import hachoir.metadata
    import hachoir.parser
except ImportError:
    hachoir = None

from . import TelegramBareClient
from . import helpers, utils, events
from .errors import (
    RPCError, UnauthorizedError, PhoneCodeEmptyError, PhoneCodeExpiredError,
    PhoneCodeHashEmptyError, PhoneCodeInvalidError, LocationInvalidError,
    SessionPasswordNeededError, FileMigrateError, PhoneNumberUnoccupiedError,
    PhoneNumberOccupiedError
)
from .network import ConnectionMode
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
    CheckChatInviteRequest, ReadMentionsRequest, SendMultiMediaRequest,
    UploadMediaRequest, EditMessageRequest, GetFullChatRequest,
    ForwardMessagesRequest
)

from .tl.functions import channels
from .tl.functions import messages

from .tl.functions.users import (
    GetUsersRequest
)
from .tl.functions.channels import (
    GetChannelsRequest, GetFullChannelRequest, GetParticipantsRequest
)
from .tl.types import (
    DocumentAttributeAudio, DocumentAttributeFilename,
    InputDocumentFileLocation, InputFileLocation,
    InputMediaUploadedDocument, InputMediaUploadedPhoto, InputPeerEmpty,
    Message, MessageMediaContact, MessageMediaDocument, MessageMediaPhoto,
    InputUserSelf, UserProfilePhoto, ChatPhoto, UpdateMessageID,
    UpdateNewChannelMessage, UpdateNewMessage, UpdateShortSentMessage,
    PeerUser, InputPeerUser, InputPeerChat, InputPeerChannel, MessageEmpty,
    ChatInvite, ChatInviteAlready, PeerChannel, Photo, InputPeerSelf,
    InputSingleMedia, InputMediaPhoto, InputPhoto, InputFile, InputFileBig,
    InputDocument, InputMediaDocument, Document, MessageEntityTextUrl,
    InputMessageEntityMentionName, DocumentAttributeVideo,
    UpdateEditMessage, UpdateEditChannelMessage, UpdateShort, Updates,
    MessageMediaWebPage, ChannelParticipantsSearch
)
from .tl.types.messages import DialogsSlice
from .extensions import markdown, html

__log__ = logging.getLogger(__name__)


class TelegramClient(TelegramBareClient):
    """
    Initializes the Telegram client with the specified API ID and Hash.

    Args:
        session (:obj:`str` | :obj:`Session` | :obj:`None`):
            The file name of the session file to be used if a string is
            given (it may be a full path), or the Session instance to be
            used otherwise. If it's ``None``, the session will not be saved,
            and you should call :meth:`.log_out()` when you're done.

        api_id (:obj:`int` | :obj:`str`):
            The API ID you obtained from https://my.telegram.org.

        api_hash (:obj:`str`):
            The API ID you obtained from https://my.telegram.org.

        connection_mode (:obj:`ConnectionMode`, optional):
            The connection mode to be used when creating a new connection
            to the servers. Defaults to the ``TCP_FULL`` mode.
            This will only affect how messages are sent over the network
            and how much processing is required before sending them.

        use_ipv6 (:obj:`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is ``False`` as IPv6 support is not
            too widespread yet.

        proxy (:obj:`tuple` | :obj:`dict`, optional):
            A tuple consisting of ``(socks.SOCKS5, 'host', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        update_workers (:obj:`int`, optional):
            If specified, represents how many extra threads should
            be spawned to handle incoming updates, and updates will
            be kept in memory until they are processed. Note that
            you must set this to at least ``0`` if you want to be
            able to process updates through :meth:`updates.poll()`.

        timeout (:obj:`int` | :obj:`float` | :obj:`timedelta`, optional):
            The timeout to be used when receiving responses from
            the network. Defaults to 5 seconds.

        spawn_read_thread (:obj:`bool`, optional):
            Whether to use an extra background thread or not. Defaults
            to ``True`` so receiving items from the network happens
            instantly, as soon as they arrive. Can still be disabled
            if you want to run the library without any additional thread.

    Kwargs:
        Extra parameters will be forwarded to the ``Session`` file.
        Most relevant parameters are:

            .. code-block:: python

                 device_model     = platform.node()
                 system_version   = platform.system()
                 app_version      = TelegramClient.__version__
                 lang_code        = 'en'
                 system_lang_code = lang_code
                 report_errors    = True
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

        self._event_builders = []
        self._events_pending_resolve = []

        # Some fields to easy signing in. Let {phone: hash} be
        # a dictionary because the user may change their mind.
        self._phone_code_hash = {}
        self._phone = None

        # Sometimes we need to know who we are, cache the self peer
        self._self_input_peer = None

    # endregion

    # region Telegram requests functions

    # region Authorization requests

    def send_code_request(self, phone, force_sms=False):
        """
        Sends a code request to the specified phone number.

        Args:
            phone (:obj:`str` | :obj:`int`):
                The phone to which the code will be sent.

            force_sms (:obj:`bool`, optional):
                Whether to force sending as SMS.

        Returns:
            Information about the result of the request.
        """
        phone = utils.parse_phone(phone) or self._phone
        phone_hash = self._phone_code_hash.get(phone)

        if not phone_hash:
            result = self(SendCodeRequest(phone, self.api_id, self.api_hash))
            self._phone_code_hash[phone] = phone_hash = result.phone_code_hash
        else:
            force_sms = True

        self._phone = phone

        if force_sms:
            result = self(ResendCodeRequest(phone, phone_hash))
            self._phone_code_hash[phone] = result.phone_code_hash

        return result

    def start(self,
              phone=lambda: input('Please enter your phone: '),
              password=lambda: getpass.getpass('Please enter your password: '),
              bot_token=None, force_sms=False, code_callback=None,
              first_name='New User', last_name=''):
        """
        Convenience method to interactively connect and sign in if required,
        also taking into consideration that 2FA may be enabled in the account.

        Example usage:
            >>> client = TelegramClient(session, api_id, api_hash).start(phone)
            Please enter the code you received: 12345
            Please enter your password: *******
            (You are now logged in)

        Args:
            phone (:obj:`str` | :obj:`int` | :obj:`callable`):
                The phone (or callable without arguments to get it)
                to which the code will be sent.

            password (:obj:`callable`, optional):
                The password for 2 Factor Authentication (2FA).
                This is only required if it is enabled in your account.

            bot_token (:obj:`str`):
                Bot Token obtained by @BotFather to log in as a bot.
                Cannot be specified with `phone` (only one of either allowed).

            force_sms (:obj:`bool`, optional):
                Whether to force sending the code request as SMS.
                This only makes sense when signing in with a `phone`.

            code_callback (:obj:`callable`, optional):
                A callable that will be used to retrieve the Telegram
                login code. Defaults to `input()`.

            first_name (:obj:`str`, optional):
                The first name to be used if signing up. This has no
                effect if the account already exists and you sign in.

            last_name (:obj:`str`, optional):
                Similar to the first name, but for the last. Optional.

        Returns:
            :obj:`TelegramClient`:
                This client, so initialization can be chained with `.start()`.
        """

        if code_callback is None:
            def code_callback():
                return input('Please enter the code you received: ')
        elif not callable(code_callback):
            raise ValueError(
                'The code_callback parameter needs to be a callable '
                'function that returns the code you received by Telegram.'
            )

        if not phone and not bot_token:
            raise ValueError('No phone number or bot token provided.')

        if phone and bot_token and not callable(phone):
            raise ValueError('Both a phone and a bot token provided, '
                             'must only provide one of either')

        if not self.is_connected():
            self.connect()

        if self.is_user_authorized():
            self._check_events_pending_resolve()
            return self

        if bot_token:
            self.sign_in(bot_token=bot_token)
            return self

        # Turn the callable into a valid phone number
        while callable(phone):
            phone = utils.parse_phone(phone()) or phone

        me = None
        attempts = 0
        max_attempts = 3
        two_step_detected = False

        sent_code = self.send_code_request(phone, force_sms=force_sms)
        sign_up = not sent_code.phone_registered
        while attempts < max_attempts:
            try:
                if sign_up:
                    me = self.sign_up(code_callback(), first_name, last_name)
                else:
                    # Raises SessionPasswordNeededError if 2FA enabled
                    me = self.sign_in(phone, code_callback())
                break
            except SessionPasswordNeededError:
                two_step_detected = True
                break
            except PhoneNumberOccupiedError:
                sign_up = False
            except PhoneNumberUnoccupiedError:
                sign_up = True
            except (PhoneCodeEmptyError, PhoneCodeExpiredError,
                    PhoneCodeHashEmptyError, PhoneCodeInvalidError):
                print('Invalid code. Please try again.', file=sys.stderr)

            attempts += 1
        else:
            raise RuntimeError(
                '{} consecutive sign-in attempts failed. Aborting'
                .format(max_attempts)
            )

        if two_step_detected:
            if not password:
                raise ValueError(
                    "Two-step verification is enabled for this account. "
                    "Please provide the 'password' argument to 'start()'."
                )
            # TODO If callable given make it retry on invalid
            if callable(password):
                password = password()
            me = self.sign_in(phone=phone, password=password)

        # We won't reach here if any step failed (exit by exception)
        print('Signed in successfully as', utils.get_display_name(me))
        self._check_events_pending_resolve()
        return self

    def sign_in(self, phone=None, code=None,
                password=None, bot_token=None, phone_code_hash=None):
        """
        Starts or completes the sign in process with the given phone number
        or code that Telegram sent.

        Args:
            phone (:obj:`str` | :obj:`int`):
                The phone to send the code to if no code was provided,
                or to override the phone that was previously used with
                these requests.

            code (:obj:`str` | :obj:`int`):
                The code that Telegram sent.

            password (:obj:`str`):
                2FA password, should be used if a previous call raised
                SessionPasswordNeededError.

            bot_token (:obj:`str`):
                Used to sign in as a bot. Not all requests will be available.
                This should be the hash the @BotFather gave you.

            phone_code_hash (:obj:`str`):
                The hash returned by .send_code_request. This can be set to None
                to use the last hash known.

        Returns:
            The signed in user, or the information about
            :meth:`.send_code_request()`.
        """
        if self.is_user_authorized():
            self._check_events_pending_resolve()
            return self.get_me()

        if phone and not code and not password:
            return self.send_code_request(phone)
        elif code:
            phone = utils.parse_phone(phone) or self._phone
            phone_code_hash = \
                phone_code_hash or self._phone_code_hash.get(phone, None)

            if not phone:
                raise ValueError(
                    'Please make sure to call send_code_request first.'
                )
            if not phone_code_hash:
                raise ValueError('You also need to provide a phone_code_hash.')

            # May raise PhoneCodeEmptyError, PhoneCodeExpiredError,
            # PhoneCodeHashEmptyError or PhoneCodeInvalidError.
            result = self(SignInRequest(phone, phone_code_hash, str(code)))
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

        self._self_input_peer = utils.get_input_peer(
            result.user, allow_self=False
        )
        self._set_connected_and_authorized()
        return result.user

    def sign_up(self, code, first_name, last_name=''):
        """
        Signs up to Telegram if you don't have an account yet.
        You must call .send_code_request(phone) first.

        Args:
            code (:obj:`str` | :obj:`int`):
                The code sent by Telegram

            first_name (:obj:`str`):
                The first name to be used by the new account.

            last_name (:obj:`str`, optional)
                Optional last name.

        Returns:
            The new created user.
        """
        if self.is_user_authorized():
            self._check_events_pending_resolve()
            return self.get_me()

        result = self(SignUpRequest(
            phone_number=self._phone,
            phone_code_hash=self._phone_code_hash.get(self._phone, ''),
            phone_code=str(code),
            first_name=first_name,
            last_name=last_name
        ))

        self._self_input_peer = utils.get_input_peer(
            result.user, allow_self=False
        )
        self._set_connected_and_authorized()
        return result.user

    def log_out(self):
        """
        Logs out Telegram and deletes the current ``*.session`` file.

        Returns:
            True if the operation was successful.
        """
        try:
            self(LogOutRequest())
        except RPCError:
            return False

        self.disconnect()
        self.session.delete()
        return True

    def get_me(self, input_peer=False):
        """
        Gets "me" (the self user) which is currently authenticated,
        or None if the request fails (hence, not authenticated).

        Args:
            input_peer (:obj:`bool`, optional):
                Whether to return the ``InputPeerUser`` version or the normal
                ``User``. This can be useful if you just need to know the ID
                of yourself.

        Returns:
            :obj:`User`: Your own user.
        """
        if input_peer and self._self_input_peer:
            return self._self_input_peer

        try:
            me = self(GetUsersRequest([InputUserSelf()]))[0]
            if not self._self_input_peer:
                self._self_input_peer = utils.get_input_peer(
                    me, allow_self=False
                )

            return self._self_input_peer if input_peer else me
        except UnauthorizedError:
            return None

    # endregion

    # region Dialogs ("chats") requests

    def get_dialogs(self, limit=10, offset_date=None, offset_id=0,
                    offset_peer=InputPeerEmpty()):
        """
        Gets N "dialogs" (open "chats" or conversations with other people).

        Args:
            limit (:obj:`int` | :obj:`None`):
                How many dialogs to be retrieved as maximum. Can be set to
                ``None`` to retrieve all dialogs. Note that this may take
                whole minutes if you have hundreds of dialogs, as Telegram
                will tell the library to slow down through a
                ``FloodWaitError``.

            offset_date (:obj:`datetime`, optional):
                The offset date to be used.

            offset_id (:obj:`int`, optional):
                The message ID to be used as an offset.

            offset_peer (:obj:`InputPeer`, optional):
                The peer to be used as an offset.

        Returns:
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
            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(r.users, r.chats)}

            for d in r.dialogs:
                dialogs[utils.get_peer_id(d.peer)] = \
                    Dialog(self, d, entities, messages)

            if len(r.dialogs) < real_limit or not isinstance(r, DialogsSlice):
                # Less than we requested means we reached the end, or
                # we didn't get a DialogsSlice which means we got all.
                break

            offset_date = r.messages[-1].date
            offset_peer = entities[utils.get_peer_id(r.dialogs[-1].peer)]
            offset_id = r.messages[-1].id

        dialogs = UserList(
            itertools.islice(dialogs.values(), min(limit, len(dialogs)))
        )
        dialogs.total = total_count
        return dialogs

    def get_drafts(self):  # TODO: Ability to provide a `filter`
        """
        Gets all open draft messages.

        Returns:
            A list of custom ``Draft`` objects that are easy to work with:
            You can call ``draft.set_message('text')`` to change the message,
            or delete it through :meth:`draft.delete()`.
        """
        response = self(GetAllDraftsRequest())
        self.session.process_entities(response)
        self.session.generate_sequence(response.seq)
        drafts = [Draft._from_update(self, u) for u in response.updates]
        return drafts

    @staticmethod
    def _get_response_message(request, result):
        """
        Extracts the response message known a request and Update result.
        The request may also be the ID of the message to match.
        """
        # Telegram seems to send updateMessageID first, then updateNewMessage,
        # however let's not rely on that just in case.
        if isinstance(request, int):
            msg_id = request
        else:
            msg_id = None
            for update in result.updates:
                if isinstance(update, UpdateMessageID):
                    if update.random_id == request.random_id:
                        msg_id = update.id
                        break

        if isinstance(result, UpdateShort):
            updates = [result.update]
        elif isinstance(result, Updates):
            updates = result.updates
        else:
            return

        for update in updates:
            if isinstance(update, (UpdateNewChannelMessage, UpdateNewMessage)):
                if update.message.id == msg_id:
                    return update.message

            elif (isinstance(update, UpdateEditMessage) and
                    not isinstance(request.peer, InputPeerChannel)):
                if request.id == update.message.id:
                    return update.message

            elif (isinstance(update, UpdateEditChannelMessage) and
                    utils.get_peer_id(request.peer) ==
                        utils.get_peer_id(update.message.to_id)):
                if request.id == update.message.id:
                    return update.message

    def _parse_message_text(self, message, parse_mode):
        """
        Returns a (parsed message, entities) tuple depending on parse_mode.
        """
        if not parse_mode:
            return message, []

        parse_mode = parse_mode.lower()
        if parse_mode in {'md', 'markdown'}:
            message, msg_entities = markdown.parse(message)
        elif parse_mode.startswith('htm'):
            message, msg_entities = html.parse(message)
        else:
            raise ValueError('Unknown parsing mode: {}'.format(parse_mode))

        for i, e in enumerate(msg_entities):
            if isinstance(e, MessageEntityTextUrl):
                m = re.match(r'^@|\+|tg://user\?id=(\d+)', e.url)
                if m:
                    try:
                        msg_entities[i] = InputMessageEntityMentionName(
                            e.offset, e.length, self.get_input_entity(
                                int(m.group(1)) if m.group(1) else e.url
                            )
                        )
                    except (ValueError, TypeError):
                        # Make no replacement
                        pass

        return message, msg_entities

    def send_message(self, entity, message='', reply_to=None, parse_mode='md',
                     link_preview=True, file=None, force_document=False):
        """
        Sends the given message to the specified entity (user/chat/channel).

        Args:
            entity (:obj:`entity`):
                To who will it be sent.

            message (:obj:`str` | :obj:`Message`):
                The message to be sent, or another message object to resend.

            reply_to (:obj:`int` | :obj:`Message`, optional):
                Whether to reply to a message or not. If an integer is provided,
                it should be the ID of the message that it should reply to.

            parse_mode (:obj:`str`, optional):
                Can be 'md' or 'markdown' for markdown-like parsing (default),
                or 'htm' or 'html' for HTML-like parsing. If ``None`` or any
                other false-y value is provided, the message will be sent with
                no formatting.

            link_preview (:obj:`bool`, optional):
                Should the link preview be shown?

            file (:obj:`file`, optional):
                Sends a message with a file attached (e.g. a photo,
                video, audio or document). The ``message`` may be empty.

            force_document (:obj:`bool`, optional):
                Whether to send the given file as a document or not.

        Returns:
            the sent message
        """
        if file is not None:
            return self.send_file(
                entity, file, caption=message, reply_to=reply_to,
                parse_mode=parse_mode, force_document=force_document
            )
        elif not message:
            raise ValueError(
                'The message cannot be empty unless a file is provided'
            )

        entity = self.get_input_entity(entity)
        if isinstance(message, Message):
            if (message.media
                    and not isinstance(message.media, MessageMediaWebPage)):
                return self.send_file(entity, message.media)

            if utils.get_peer_id(entity) == utils.get_peer_id(message.to_id):
                reply_id = message.reply_to_msg_id
            else:
                reply_id = None
            request = SendMessageRequest(
                peer=entity,
                message=message.message or '',
                silent=message.silent,
                reply_to_msg_id=reply_id,
                reply_markup=message.reply_markup,
                entities=message.entities,
                no_webpage=not isinstance(message.media, MessageMediaWebPage)
            )
            message = message.message
        else:
            message, msg_ent = self._parse_message_text(message, parse_mode)
            request = SendMessageRequest(
                peer=entity,
                message=message,
                entities=msg_ent,
                no_webpage=not link_preview,
                reply_to_msg_id=self._get_message_id(reply_to)
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

        return self._get_response_message(request, result)

    def forward_messages(self, entity, messages, from_peer=None):
        """
        Forwards the given message(s) to the specified entity.

        Args:
            entity (:obj:`entity`):
                To which entity the message(s) will be forwarded.

            messages (:obj:`list` | :obj:`int` | :obj:`Message`):
                The message(s) to forward, or their integer IDs.

            from_peer (:obj:`entity`):
                If the given messages are integer IDs and not instances
                of the ``Message`` class, this *must* be specified in
                order for the forward to work.

        Returns:
            The forwarded messages.
        """
        if not utils.is_list_like(messages):
            messages = (messages,)

        if not from_peer:
            try:
                # On private chats (to_id = PeerUser), if the message is
                # not outgoing, we actually need to use "from_id" to get
                # the conversation on which the message was sent.
                from_peer = next(
                    m.from_id if not m.out and isinstance(m.to_id, PeerUser)
                    else m.to_id for m in messages if isinstance(m, Message)
                )
            except StopIteration:
                raise ValueError(
                    'from_chat must be given if integer IDs are used'
                )

        req = ForwardMessagesRequest(
            from_peer=from_peer,
            id=[m if isinstance(m, int) else m.id for m in messages],
            to_peer=entity
        )
        result = self(req)
        random_to_id = {}
        id_to_message = {}
        for update in result.updates:
            if isinstance(update, UpdateMessageID):
                random_to_id[update.random_id] = update.id
            elif isinstance(update, UpdateNewMessage):
                id_to_message[update.message.id] = update.message

        return [id_to_message[random_to_id[rnd]] for rnd in req.random_id]

    def edit_message(self, entity, message_id, message=None, parse_mode='md',
                     link_preview=True):
        """
        Edits the given message ID (to change its contents or disable preview).

        Args:
            entity (:obj:`entity`):
                From which chat to edit the message.

            message_id (:obj:`str`):
                The ID of the message (or ``Message`` itself) to be edited.

            message (:obj:`str`, optional):
                The new text of the message.

            parse_mode (:obj:`str`, optional):
                Can be 'md' or 'markdown' for markdown-like parsing (default),
                or 'htm' or 'html' for HTML-like parsing. If ``None`` or any
                other false-y value is provided, the message will be sent with
                no formatting.

            link_preview (:obj:`bool`, optional):
                Should the link preview be shown?

        Raises:
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but try editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

        Returns:
            the edited message
        """
        message, msg_entities = self._parse_message_text(message, parse_mode)
        request = EditMessageRequest(
            peer=self.get_input_entity(entity),
            id=self._get_message_id(message_id),
            message=message,
            no_webpage=not link_preview,
            entities=msg_entities
        )
        result = self(request)
        return self._get_response_message(request, result)

    def delete_messages(self, entity, message_ids, revoke=True):
        """
        Deletes a message from a chat, optionally "for everyone".

        Args:
            entity (:obj:`entity`):
                From who the message will be deleted. This can actually
                be ``None`` for normal chats, but **must** be present
                for channels and megagroups.

            message_ids (:obj:`list` | :obj:`int` | :obj:`Message`):
                The IDs (or ID) or messages to be deleted.

            revoke (:obj:`bool`, optional):
                Whether the message should be deleted for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will delete the message for everyone.
                This has no effect on channels or megagroups.

        Returns:
            The affected messages.
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

    def get_message_history(self, entity, limit=20, offset_date=None,
                            offset_id=0, max_id=0, min_id=0, add_offset=0, 
                            batch_size=100, wait_time=None):
        """
        Gets the message history for the specified entity

        Args:
            entity (:obj:`entity`):
                The entity from whom to retrieve the message history.

            limit (:obj:`int` | :obj:`None`, optional):
                Number of messages to be retrieved. Due to limitations with
                the API retrieving more than 3000 messages will take longer
                than half a minute (or even more based on previous calls).
                The limit may also be ``None``, which would eventually return
                the whole history.

            offset_date (:obj:`datetime`):
                Offset date (messages *previous* to this date will be
                retrieved). Exclusive.

            offset_id (:obj:`int`):
                Offset message ID (only messages *previous* to the given
                ID will be retrieved). Exclusive.

            max_id (:obj:`int`):
                All the messages with a higher (newer) ID or equal to this will
                be excluded

            min_id (:obj:`int`):
                All the messages with a lower (older) ID or equal to this will
                be excluded.

            add_offset (:obj:`int`):
                Additional message offset (all of the specified offsets +
                this offset = older messages).

            batch_size (:obj:`int`):
                Messages will be returned in chunks of this size (100 is
                the maximum). While it makes no sense to modify this value,
                you are still free to do so.

            wait_time (:obj:`int`):
                Wait time between different ``GetHistoryRequest``. Use this
                parameter to avoid hitting the ``FloodWaitError`` as needed.
                If left to ``None``, it will default to 1 second only if
                the limit is higher than 3000.

        Returns:
            A list of messages with extra attributes:

                * ``.total`` = (on the list) total amount of messages sent.
                * ``.sender`` = entity of the sender.
                * ``.fwd_from.sender`` = if fwd_from, who sent it originally.
                * ``.fwd_from.channel`` = if fwd_from, original channel.
                * ``.to`` = entity to which the message was sent.

        Notes:
            Telegram's flood wait limit for ``GetHistoryRequest`` seems to
            be around 30 seconds per 3000 messages, therefore a sleep of 1
            second is the default for this limit (or above). You may need
            an higher limit, so you're free to set the ``batch_size`` that
            you think may be good.

        """
        entity = self.get_input_entity(entity)
        limit = float('inf') if limit is None else int(limit)
        if limit == 0:
            # No messages, but we still need to know the total message count
            result = self(GetHistoryRequest(
                peer=entity, limit=1,
                offset_date=None, offset_id=0, max_id=0, min_id=0,
                add_offset=0, hash=0
            ))
            return getattr(result, 'count', len(result.messages)), [], []

        if wait_time is None:
            wait_time = 1 if limit > 3000 else 0

        batch_size = min(max(batch_size, 1), 100)
        total_messages = 0
        messages = UserList()
        entities = {}
        while len(messages) < limit:
            # Telegram has a hard limit of 100
            real_limit = min(limit - len(messages), batch_size)
            result = self(GetHistoryRequest(
                peer=entity,
                limit=real_limit,
                offset_date=offset_date,
                offset_id=offset_id,
                max_id=max_id,
                min_id=min_id,
                add_offset=add_offset,
                hash=0
            ))
            messages.extend(
                m for m in result.messages if not isinstance(m, MessageEmpty)
            )
            total_messages = getattr(result, 'count', len(result.messages))

            for u in result.users:
                entities[utils.get_peer_id(u)] = u
            for c in result.chats:
                entities[utils.get_peer_id(c)] = c

            if len(result.messages) < real_limit:
                break

            offset_id = result.messages[-1].id
            offset_date = result.messages[-1].date
            time.sleep(wait_time)

        # Add a few extra attributes to the Message to make it friendlier.
        messages.total = total_messages
        for m in messages:
            # To make messages more friendly, always add message
            # to service messages, and action to normal messages.
            m.message = getattr(m, 'message', None)
            m.action = getattr(m, 'action', None)
            m.sender = (None if not m.from_id else
                        entities[utils.get_peer_id(m.from_id)])

            if getattr(m, 'fwd_from', None):
                m.fwd_from.sender = (
                    None if not m.fwd_from.from_id else
                    entities[utils.get_peer_id(m.fwd_from.from_id)]
                )
                m.fwd_from.channel = (
                    None if not m.fwd_from.channel_id else
                    entities[utils.get_peer_id(
                        PeerChannel(m.fwd_from.channel_id)
                    )]
                )

            m.to = entities[utils.get_peer_id(m.to_id)]

        return messages

    def send_read_acknowledge(self, entity, message=None, max_id=None,
                              clear_mentions=False):
        """
        Sends a "read acknowledge" (i.e., notifying the given peer that we've
        read their messages, also known as the "double check").

        Args:
            entity (:obj:`entity`):
                The chat where these messages are located.

            message (:obj:`list` | :obj:`Message`):
                Either a list of messages or a single message.

            max_id (:obj:`int`):
                Overrides messages, until which message should the
                acknowledge should be sent.

            clear_mentions (:obj:`bool`):
                Whether the mention badge should be cleared (so that
                there are no more mentions) or not for the given entity.

                If no message is provided, this will be the only action
                taken.
        """
        if max_id is None:
            if message:
                if utils.is_list_like(message):
                    max_id = max(msg.id for msg in message)
                else:
                    max_id = message.id
            elif not clear_mentions:
                raise ValueError(
                    'Either a message list or a max_id must be provided.')

        entity = self.get_input_entity(entity)
        if clear_mentions:
            self(ReadMentionsRequest(entity))
            if max_id is None:
                return True

        if max_id is not None:
            if isinstance(entity, InputPeerChannel):
                return self(channels.ReadHistoryRequest(entity, max_id=max_id))
            else:
                return self(messages.ReadHistoryRequest(entity, max_id=max_id))

        return False

    @staticmethod
    def _get_message_id(message):
        """Sanitizes the 'reply_to' parameter a user may send"""
        if message is None:
            return None

        if isinstance(message, int):
            return message

        try:
            if message.SUBCLASS_OF_ID == 0x790009e3:
                # hex(crc32(b'Message')) = 0x790009e3
                return message.id
        except AttributeError:
            pass

        raise TypeError('Invalid message type: {}'.format(type(message)))

    def get_participants(self, entity, limit=None, search='',
                         aggressive=False):
        """
        Gets the list of participants from the specified entity.

        Args:
            entity (:obj:`entity`):
                The entity from which to retrieve the participants list.

            limit (:obj:`int`):
                Limits amount of participants fetched.

            search (:obj:`str`, optional):
                Look for participants with this string in name/username.

            aggressive (:obj:`bool`, optional):
                Aggressively looks for all participants in the chat in
                order to get more than 10,000 members (a hard limit
                imposed by Telegram). Note that this might take a long
                time (over 5 minutes), but is able to return over 90,000
                participants on groups with 100,000 members.

                This has no effect for groups or channels with less than
                10,000 members.

        Returns:
            A list of participants with an additional .total variable on the
            list indicating the total amount of members in this group/channel.
        """
        entity = self.get_input_entity(entity)
        limit = float('inf') if limit is None else int(limit)
        if isinstance(entity, InputPeerChannel):
            total = self(GetFullChannelRequest(
                entity
            )).full_chat.participants_count
            if limit == 0:
                users = UserList()
                users.total = total
                return users

            all_participants = {}
            if total > 10000 and aggressive:
                requests = [GetParticipantsRequest(
                    channel=entity,
                    filter=ChannelParticipantsSearch(search + chr(x)),
                    offset=0,
                    limit=200,
                    hash=0
                ) for x in range(ord('a'), ord('z') + 1)]
            else:
                requests = [GetParticipantsRequest(
                    channel=entity,
                    filter=ChannelParticipantsSearch(search),
                    offset=0,
                    limit=200,
                    hash=0
                )]

            while requests:
                # Only care about the limit for the first request
                # (small amount of people, won't be aggressive).
                #
                # Most people won't care about getting exactly 12,345
                # members so it doesn't really matter not to be 100%
                # precise with being out of the offset/limit here.
                requests[0].limit = min(limit - requests[0].offset, 200)
                if requests[0].offset > limit:
                    break

                if len(requests) == 1:
                    results = (self(requests[0]),)
                else:
                    results = self(*requests)
                for i in reversed(range(len(requests))):
                    participants = results[i]
                    if not participants.users:
                        requests.pop(i)
                    else:
                        requests[i].offset += len(participants.users)
                        for user in participants.users:
                            if len(all_participants) < limit:
                                all_participants[user.id] = user
            if limit < float('inf'):
                values = itertools.islice(all_participants.values(), limit)
            else:
                values = all_participants.values()

            users = UserList(values)
            users.total = total
        elif isinstance(entity, InputPeerChat):
            users = self(GetFullChatRequest(entity.chat_id)).users
            if len(users) > limit:
                users = users[:limit]
            users = UserList(users)
            users.total = len(users)
        else:
            users = UserList(None if limit == 0 else [entity])
            users.total = 1
        return users

    # endregion

    # region Uploading files

    def send_file(self, entity, file, caption='',
                  force_document=False, progress_callback=None,
                  reply_to=None,
                  attributes=None,
                  thumb=None,
                  allow_cache=True,
                  parse_mode='md',
                  **kwargs):
        """
        Sends a file to the specified entity.

        Args:
            entity (:obj:`entity`):
                Who will receive the file.

            file (:obj:`str` | :obj:`bytes` | :obj:`file` | :obj:`media`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

                Subsequent calls with the very same file will result in
                immediate uploads, unless ``.clear_file_cache()`` is called.

                Furthermore the file may be any media (a message, document,
                photo or similar) so that it can be resent without the need
                to download and re-upload it again.

            caption (:obj:`str`, optional):
                Optional caption for the sent media message.

            force_document (:obj:`bool`, optional):
                If left to ``False`` and the file is a path that ends with
                the extension of an image file or a video file, it will be
                sent as such. Otherwise always as a document.

            progress_callback (:obj:`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

            reply_to (:obj:`int` | :obj:`Message`):
                Same as reply_to from .send_message().

            attributes (:obj:`list`, optional):
                Optional attributes that override the inferred ones, like
                ``DocumentAttributeFilename`` and so on.

            thumb (:obj:`str` | :obj:`bytes` | :obj:`file`, optional):
                Optional thumbnail (for videos).

            allow_cache (:obj:`bool`, optional):
                Whether to allow using the cached version stored in the
                database or not. Defaults to ``True`` to avoid re-uploads.
                Must be ``False`` if you wish to use different attributes
                or thumb than those that were used when the file was cached.

            parse_mode (:obj:`str`, optional):
                The parse mode for the caption message.

        Kwargs:
           If "is_voice_note" in kwargs, despite its value, and the file is
           sent as a document, it will be sent as a voice note.

        Notes:
            If the ``hachoir3`` package (``hachoir`` module) is installed,
            it will be used to determine metadata from audio and video files.

        Returns:
            The message (or messages) containing the sent file.
        """
        # First check if the user passed an iterable, in which case
        # we may want to send as an album if all are photo files.
        if utils.is_list_like(file):
            # Convert to tuple so we can iterate several times
            file = tuple(x for x in file)
            if all(utils.is_image(x) for x in file):
                return self._send_album(
                    entity, file, caption=caption,
                    progress_callback=progress_callback, reply_to=reply_to,
                    parse_mode=parse_mode
                )
            # Not all are images, so send all the files one by one
            return [
                self.send_file(
                    entity, x, allow_cache=False,
                    caption=caption, force_document=force_document,
                    progress_callback=progress_callback, reply_to=reply_to,
                    attributes=attributes, thumb=thumb, **kwargs
                ) for x in file
            ]

        entity = self.get_input_entity(entity)
        reply_to = self._get_message_id(reply_to)
        caption, msg_entities = self._parse_message_text(caption, parse_mode)

        if not isinstance(file, (str, bytes, io.IOBase)):
            # The user may pass a Message containing media (or the media,
            # or anything similar) that should be treated as a file. Try
            # getting the input media for whatever they passed and send it.
            try:
                media = utils.get_input_media(file)
            except TypeError:
                pass  # Can't turn whatever was given into media
            else:
                request = SendMediaRequest(entity, media,
                                           reply_to_msg_id=reply_to,
                                           message=caption,
                                           entities=msg_entities)
                return self._get_response_message(request, self(request))

        as_image = utils.is_image(file) and not force_document
        use_cache = InputPhoto if as_image else InputDocument
        file_handle = self.upload_file(
            file, progress_callback=progress_callback,
            use_cache=use_cache if allow_cache else None
        )

        if isinstance(file_handle, use_cache):
            # File was cached, so an instance of use_cache was returned
            if as_image:
                media = InputMediaPhoto(file_handle)
            else:
                media = InputMediaDocument(file_handle)
        elif as_image:
            media = InputMediaUploadedPhoto(file_handle)
        else:
            mime_type = None
            if isinstance(file, str):
                # Determine mime-type and attributes
                # Take the first element by using [0] since it returns a tuple
                mime_type = guess_type(file)[0]
                attr_dict = {
                    DocumentAttributeFilename:
                        DocumentAttributeFilename(os.path.basename(file))
                }
                if utils.is_audio(file) and hachoir:
                    m = hachoir.metadata.extractMetadata(
                        hachoir.parser.createParser(file)
                    )
                    attr_dict[DocumentAttributeAudio] = DocumentAttributeAudio(
                        title=m.get('title') if m.has('title') else None,
                        performer=m.get('author') if m.has('author') else None,
                        duration=int(m.get('duration').seconds
                                     if m.has('duration') else 0)
                    )

                if not force_document and utils.is_video(file):
                    if hachoir:
                        m = hachoir.metadata.extractMetadata(
                            hachoir.parser.createParser(file)
                        )
                        doc = DocumentAttributeVideo(
                            w=m.get('width') if m.has('width') else 0,
                            h=m.get('height') if m.has('height') else 0,
                            duration=int(m.get('duration').seconds
                                         if m.has('duration') else 0)
                        )
                    else:
                        doc = DocumentAttributeVideo(0, 0, 0)
                    attr_dict[DocumentAttributeVideo] = doc
            else:
                attr_dict = {
                    DocumentAttributeFilename: DocumentAttributeFilename(
                        os.path.basename(
                            getattr(file, 'name', None) or 'unnamed'))
                }

            if 'is_voice_note' in kwargs:
                if DocumentAttributeAudio in attr_dict:
                    attr_dict[DocumentAttributeAudio].voice = True
                else:
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

            input_kw = {}
            if thumb:
                input_kw['thumb'] = self.upload_file(thumb)

            media = InputMediaUploadedDocument(
                file=file_handle,
                mime_type=mime_type,
                attributes=list(attr_dict.values()),
                **input_kw
            )

        # Once the media type is properly specified and the file uploaded,
        # send the media message to the desired entity.
        request = SendMediaRequest(entity, media, reply_to_msg_id=reply_to,
                                   message=caption, entities=msg_entities)
        msg = self._get_response_message(request, self(request))
        if msg and isinstance(file_handle, InputSizedFile):
            # There was a response message and we didn't use cached
            # version, so cache whatever we just sent to the database.
            md5, size = file_handle.md5, file_handle.size
            if as_image:
                to_cache = utils.get_input_photo(msg.media.photo)
            else:
                to_cache = utils.get_input_document(msg.media.document)
            self.session.cache_file(md5, size, to_cache)

        return msg

    def send_voice_note(self, *args, **kwargs):
        """Wrapper method around .send_file() with is_voice_note=True"""
        kwargs['is_voice_note'] = True
        return self.send_file(*args, **kwargs)

    def _send_album(self, entity, files, caption='',
                    progress_callback=None, reply_to=None,
                    parse_mode='md'):
        """Specialized version of .send_file for albums"""
        # We don't care if the user wants to avoid cache, we will use it
        # anyway. Why? The cached version will be exactly the same thing
        # we need to produce right now to send albums (uploadMedia), and
        # cache only makes a difference for documents where the user may
        # want the attributes used on them to change.
        entity = self.get_input_entity(entity)
        if not utils.is_list_like(caption):
            caption = (caption,)
        captions = [
            self._parse_message_text(caption or '', parse_mode)
            for caption in reversed(caption)  # Pop from the end (so reverse)
        ]
        reply_to = self._get_message_id(reply_to)

        # Need to upload the media first, but only if they're not cached yet
        media = []
        for file in files:
            # fh will either be InputPhoto or a modified InputFile
            fh = self.upload_file(file, use_cache=InputPhoto)
            if not isinstance(fh, InputPhoto):
                input_photo = utils.get_input_photo(self(UploadMediaRequest(
                    entity, media=InputMediaUploadedPhoto(fh)
                )).photo)
                self.session.cache_file(fh.md5, fh.size, input_photo)
                fh = input_photo

            if captions:
                caption, msg_entities = captions.pop()
            else:
                caption, msg_entities = '', None
            media.append(InputSingleMedia(InputMediaPhoto(fh), message=caption,
                                          entities=msg_entities))

        # Now we can construct the multi-media request
        result = self(SendMultiMediaRequest(
            entity, reply_to_msg_id=reply_to, multi_media=media
        ))
        return [
            self._get_response_message(update.id, result)
            for update in result.updates
            if isinstance(update, UpdateMessageID)
        ]

    def upload_file(self,
                    file,
                    part_size_kb=None,
                    file_name=None,
                    use_cache=None,
                    progress_callback=None):
        """
        Uploads the specified file and returns a handle (an instance of
        InputFile or InputFileBig, as required) which can be later used
        before it expires (they are usable during less than a day).

        Uploading a file will simply return a "handle" to the file stored
        remotely in the Telegram servers, which can be later used on. This
        will **not** upload the file to your own chat or any chat at all.

        Args:
            file (:obj:`str` | :obj:`bytes` | :obj:`file`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

                Subsequent calls with the very same file will result in
                immediate uploads, unless ``.clear_file_cache()`` is called.

            part_size_kb (:obj:`int`, optional):
                Chunk size when uploading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_name (:obj:`str`, optional):
                The file name which will be used on the resulting InputFile.
                If not specified, the name will be taken from the ``file``
                and if this is not a ``str``, it will be ``"unnamed"``.

            use_cache (:obj:`type`, optional):
                The type of cache to use (currently either ``InputDocument``
                or ``InputPhoto``). If present and the file is small enough
                to need the MD5, it will be checked against the database,
                and if a match is found, the upload won't be made. Instead,
                an instance of type ``use_cache`` will be returned.

            progress_callback (:obj:`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

        Returns:
            ``InputFileBig`` if the file size is larger than 10MB,
            ``InputSizedFile`` (subclass of ``InputFile``) otherwise.
        """
        if isinstance(file, (InputFile, InputFileBig)):
            return file  # Already uploaded

        if isinstance(file, str):
            file_size = os.path.getsize(file)
        elif isinstance(file, bytes):
            file_size = len(file)
        else:
            file = file.read()
            file_size = len(file)

        # File will now either be a string or bytes
        if not part_size_kb:
            part_size_kb = utils.get_appropriated_part_size(file_size)

        if part_size_kb > 512:
            raise ValueError('The part size must be less or equal to 512KB')

        part_size = int(part_size_kb * 1024)
        if part_size % 1024 != 0:
            raise ValueError(
                'The part size must be evenly divisible by 1024')

        # Set a default file name if None was specified
        file_id = helpers.generate_random_long()
        if not file_name:
            if isinstance(file, str):
                file_name = os.path.basename(file)
            else:
                file_name = str(file_id)

        # Determine whether the file is too big (over 10MB) or not
        # Telegram does make a distinction between smaller or larger files
        is_large = file_size > 10 * 1024 * 1024
        hash_md5 = hashlib.md5()
        if not is_large:
            # Calculate the MD5 hash before anything else.
            # As this needs to be done always for small files,
            # might as well do it before anything else and
            # check the cache.
            if isinstance(file, str):
                with open(file, 'rb') as stream:
                    file = stream.read()
            hash_md5.update(file)
            if use_cache:
                cached = self.session.get_file(
                    hash_md5.digest(), file_size, cls=use_cache
                )
                if cached:
                    return cached

        part_count = (file_size + part_size - 1) // part_size
        __log__.info('Uploading file of %d bytes in %d chunks of %d',
                     file_size, part_count, part_size)

        with open(file, 'rb') if isinstance(file, str) else BytesIO(file) \
                as stream:
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
                    __log__.debug('Uploaded %d/%d', part_index + 1,
                                  part_count)
                    if progress_callback:
                        progress_callback(stream.tell(), file_size)
                else:
                    raise RuntimeError(
                        'Failed to upload file part {}.'.format(part_index))

        if is_large:
            return InputFileBig(file_id, part_count, file_name)
        else:
            return InputSizedFile(
                file_id, part_count, file_name, md5=hash_md5, size=file_size
            )

    # endregion

    # region Downloading media requests

    def download_profile_photo(self, entity, file=None, download_big=True):
        """
        Downloads the profile photo of the given entity (user/chat/channel).

        Args:
            entity (:obj:`entity`):
                From who the photo will be downloaded.

            file (:obj:`str` | :obj:`file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

            download_big (:obj:`bool`, optional):
                Whether to use the big version of the available photos.

        Returns:
            ``None`` if no photo was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
        """
        photo = entity
        possible_names = []
        try:
            is_entity = entity.SUBCLASS_OF_ID in (
                0x2da17977, 0xc5af5d94, 0x1f4661b9, 0xd49a2697
            )
        except AttributeError:
            return None  # Not even a TLObject as attribute access failed

        if is_entity:
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

        message (:obj:`Message` | :obj:`Media`):
            The media or message containing the media that will be downloaded.

        file (:obj:`str` | :obj:`file`, optional):
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.

        progress_callback (:obj:`callable`, optional):
            A callback function accepting two parameters:
            ``(recv bytes, total)``.

        Returns:
            ``None`` if no media was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
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
        elif isinstance(media, (MessageMediaDocument, Document)):
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

    def _download_document(self, document, file, date, progress_callback):
        """Specialized version of .download_media() for documents"""
        if isinstance(document, MessageMediaDocument):
            document = document.document
        if not isinstance(document, Document):
            return

        file_size = document.size

        kind = 'document'
        possible_names = []
        for attr in document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                possible_names.insert(0, attr.file_name)

            elif isinstance(attr, DocumentAttributeAudio):
                kind = 'audio'
                if attr.performer and attr.title:
                    possible_names.append('{} - {}'.format(
                        attr.performer, attr.title
                    ))
                elif attr.performer:
                    possible_names.append(attr.performer)
                elif attr.title:
                    possible_names.append(attr.title)
                elif attr.voice:
                    kind = 'voice'

        file = self._get_proper_filename(
            file, kind, utils.get_extension(document),
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

    def download_file(self,
                      input_location,
                      file,
                      part_size_kb=None,
                      file_size=None,
                      progress_callback=None):
        """
        Downloads the given input location to a file.

        Args:
            input_location (:obj:`InputFileLocation`):
                The file location from which the file will be downloaded.

            file (:obj:`str` | :obj:`file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

            part_size_kb (:obj:`int`, optional):
                Chunk size when downloading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_size (:obj:`int`, optional):
                The file size that is about to be downloaded, if known.
                Only used if ``progress_callback`` is specified.

            progress_callback (:obj:`callable`, optional):
                A callback function accepting two parameters:
                ``(downloaded bytes, total)``. Note that the
                ``total`` is the provided ``file_size``.
        """
        if not part_size_kb:
            if not file_size:
                part_size_kb = 64  # Reasonable default
            else:
                part_size_kb = utils.get_appropriated_part_size(file_size)

        part_size = int(part_size_kb * 1024)
        # https://core.telegram.org/api/files says:
        # > part_size % 1024 = 0 (divisible by 1KB)
        #
        # But https://core.telegram.org/cdn (more recent) says:
        # > limit must be divisible by 4096 bytes
        # So we just stick to the 4096 limit.
        if part_size % 4096 != 0:
            raise ValueError(
                'The part size must be evenly divisible by 4096.')

        if isinstance(file, str):
            # Ensure that we'll be able to download the media
            helpers.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        # The used client will change if FileMigrateError occurs
        client = self
        cdn_decrypter = None

        __log__.info('Downloading file in chunks of %d bytes', part_size)
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
                            __log__.info('File lives in a CDN')
                            cdn_decrypter, result = \
                                CdnDecrypter.prepare_decrypter(
                                    client, self._get_cdn_client(result),
                                    result
                                )

                except FileMigrateError as e:
                    __log__.info('File lives in another DC')
                    client = self._get_exported_client(e.new_dc)
                    continue

                offset += part_size

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    # Return some extra information, unless it's a CDN file
                    return getattr(result, 'type', '')

                f.write(result.bytes)
                __log__.debug('Saved %d more bytes', len(result.bytes))
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

    # endregion

    # region Event handling

    def on(self, event):
        """
        Decorator helper method around add_event_handler().

        Args:
            event (:obj:`_EventBuilder` | :obj:`type`):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.
        """
        def decorator(f):
            self.add_event_handler(f, event)
            return f

        return decorator

    def _check_events_pending_resolve(self):
        if self._events_pending_resolve:
            for event in self._events_pending_resolve:
                event.resolve(self)
            self._events_pending_resolve.clear()

    def _on_handler(self, update):
        for builder, callback in self._event_builders:
            event = builder.build(update)
            if event:
                event._client = self
                try:
                    callback(event)
                except events.StopPropagation:
                    __log__.debug(
                        "Event handler '{}' stopped chain of "
                        "propagation for event {}."
                        .format(callback.__name__, type(event).__name__)
                    )
                    break

    def add_event_handler(self, callback, event=None):
        """
        Registers the given callback to be called on the specified event.

        Args:
            callback (:obj:`callable`):
                The callable function accepting one parameter to be used.

            event (:obj:`_EventBuilder` | :obj:`type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, ``events.Raw`` (the ``Update`` objects
                with no further processing) will be passed instead.
        """
        if self.updates.workers is None:
            warnings.warn(
                "You have not setup any workers, so you won't receive updates."
                " Pass update_workers=1 when creating the TelegramClient,"
                " or set client.self.updates.workers = 1"
            )

        self.updates.handler = self._on_handler
        if isinstance(event, type):
            event = event()
        elif not event:
            event = events.Raw()

        if self.is_user_authorized():
            event.resolve(self)
            self._check_events_pending_resolve()
        else:
            self._events_pending_resolve.append(event)

        self._event_builders.append((event, callback))

    def add_update_handler(self, handler):
        """Adds an update handler (a function which takes a TLObject,
          an update, as its parameter) and listens for updates"""
        warnings.warn(
            'add_update_handler is deprecated, use the @client.on syntax '
            'or add_event_handler(callback, events.Raw) instead (see '
            'https://telethon.rtfd.io/en/latest/extra/basic/working-'
            'with-updates.html)'
        )
        self.add_event_handler(handler, events.Raw)

    def remove_update_handler(self, handler):
        pass

    def list_update_handlers(self):
        return []

    # endregion

    # region Small utilities to make users' life easier

    def _set_connected_and_authorized(self):
        super()._set_connected_and_authorized()
        self._check_events_pending_resolve()

    def get_entity(self, entity):
        """
        Turns the given entity into a valid Telegram user or chat.

        entity (:obj:`str` | :obj:`int` | :obj:`Peer` | :obj:`InputPeer`):
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

        Returns:
            ``User``, ``Chat`` or ``Channel`` corresponding to the input
            entity.
        """
        if utils.is_list_like(entity):
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
            utils.get_peer_id(x): x
            for x in itertools.chain(users, chats, channels)
        }

        # We could check saved usernames and put them into the users,
        # chats and channels list from before. While this would reduce
        # the amount of ResolveUsername calls, it would fail to catch
        # username changes.
        result = [
            self._get_entity_from_string(x) if isinstance(x, str)
            else id_entity[utils.get_peer_id(x)]
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
            username, is_join_chat = utils.parse_username(string)
            if is_join_chat:
                invite = self(CheckChatInviteRequest(username))
                if isinstance(invite, ChatInvite):
                    raise ValueError(
                        'Cannot get entity from a channel '
                        '(or group) that you are not part of'
                    )
                elif isinstance(invite, ChatInviteAlready):
                    return invite.chat
            elif username:
                if username in ('me', 'self'):
                    return self.get_me()
                result = self(ResolveUsernameRequest(username))
                for entity in itertools.chain(result.users, result.chats):
                    if entity.username.lower() == username:
                        return entity
            try:
                # Nobody with this username, maybe it's an exact name/title
                return self.get_entity(self.session.get_input_entity(string))
            except ValueError:
                pass

        raise TypeError(
            'Cannot turn "{}" into any entity (user or chat)'.format(string)
        )

    def get_input_entity(self, peer):
        """
        Turns the given peer into its input entity version. Most requests
        use this kind of InputUser, InputChat and so on, so this is the
        most suitable call to make for those cases.

        entity (:obj:`str` | :obj:`int` | :obj:`Peer` | :obj:`InputPeer`):
            The integer ID of an user or otherwise either of a
            ``PeerUser``, ``PeerChat`` or ``PeerChannel``, for
            which to get its ``Input*`` version.

            If this ``Peer`` hasn't been seen before by the library, the top
            dialogs will be loaded and their entities saved to the session
            file (unless this feature was disabled explicitly).

            If in the end the access hash required for the peer was not found,
            a ValueError will be raised.

        Returns:
            ``InputPeerUser``, ``InputPeerChat`` or ``InputPeerChannel``.
        """
        try:
            # First try to get the entity from cache, otherwise figure it out
            return self.session.get_input_entity(peer)
        except ValueError:
            pass

        if isinstance(peer, str):
            if peer in ('me', 'self'):
                return InputPeerSelf()
            return utils.get_input_peer(self._get_entity_from_string(peer))

        if isinstance(peer, int):
            peer, kind = utils.resolve_id(peer)
            peer = kind(peer)

        try:
            is_peer = peer.SUBCLASS_OF_ID == 0x2d45687  # crc32(b'Peer')
            if not is_peer:
                return utils.get_input_peer(peer)
        except (AttributeError, TypeError):
            is_peer = False

        if not is_peer:
            raise TypeError(
                'Cannot turn "{}" into an input entity.'.format(peer)
            )

        # Not found, look in the dialogs with the hope to find it.
        target_id = utils.get_peer_id(peer)
        req = GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=100
        )
        while True:
            result = self(req)
            entities = {}
            for x in itertools.chain(result.users, result.chats):
                x_id = utils.get_peer_id(x)
                if x_id == target_id:
                    return utils.get_input_peer(x)
                else:
                    entities[x_id] = x
            if len(result.dialogs) < req.limit:
                break

            req.offset_id = result.messages[-1].id
            req.offset_date = result.messages[-1].date
            req.offset_peer = entities[utils.get_peer_id(
                result.dialogs[-1].peer
            )]
            time.sleep(1)

        raise TypeError(
            'Could not find the input entity corresponding to "{}". '
            'Make sure you have encountered this peer before.'.format(peer)
        )

    # endregion
