import asyncio
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
from collections import UserList
from datetime import datetime, timedelta
from io import BytesIO
from mimetypes import guess_type

from async_generator import async_generator, yield_

from .crypto import CdnDecrypter
from .tl import TLObject
from .tl.custom import InputSizedFile
from .tl.functions.updates import GetDifferenceRequest
from .tl.functions.upload import (
    SaveBigFilePartRequest, SaveFilePartRequest, GetFileRequest
)
from .tl.types.updates import (
    DifferenceSlice, DifferenceEmpty, Difference, DifferenceTooLong
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
    PhoneNumberOccupiedError, UsernameNotOccupiedError
)
from .network import ConnectionTcpFull
from .tl.custom import Draft, Dialog
from .tl.functions.account import (
    GetPasswordRequest, UpdatePasswordSettingsRequest
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
    ForwardMessagesRequest, SearchRequest
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
    MessageMediaWebPage, ChannelParticipantsSearch, PhotoSize, PhotoCachedSize,
    PhotoSizeEmpty, MessageService, ChatParticipants, User, WebPage,
    ChannelParticipantsBanned, ChannelParticipantsKicked,
    InputMessagesFilterEmpty
)
from .tl.types.messages import DialogsSlice
from .tl.types.account import PasswordInputSettings, NoPassword
from .extensions import markdown, html

__log__ = logging.getLogger(__name__)


class TelegramClient(TelegramBareClient):
    """
    Initializes the Telegram client with the specified API ID and Hash.

    Args:
        session (`str` | `telethon.sessions.abstract.Session`, `None`):
            The file name of the session file to be used if a string is
            given (it may be a full path), or the Session instance to be
            used otherwise. If it's ``None``, the session will not be saved,
            and you should call :meth:`.log_out()` when you're done.

            Note that if you pass a string it will be a file in the current
            working directory, although you can also pass absolute paths.

            The session file contains enough information for you to login
            without re-sending the code, so if you have to enter the code
            more than once, maybe you're changing the working directory,
            renaming or removing the file, or using random names.

        api_id (`int` | `str`):
            The API ID you obtained from https://my.telegram.org.

        api_hash (`str`):
            The API ID you obtained from https://my.telegram.org.

        connection (`telethon.network.connection.common.Connection`, optional):
            The connection instance to be used when creating a new connection
            to the servers. If it's a type, the `proxy` argument will be used.

            Defaults to `telethon.network.connection.tcpfull.ConnectionTcpFull`.

        use_ipv6 (`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is ``False`` as IPv6 support is not
            too widespread yet.

        proxy (`tuple` | `dict`, optional):
            A tuple consisting of ``(socks.SOCKS5, 'host', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        update_workers (`int`, optional):
            If specified, represents how many extra threads should
            be spawned to handle incoming updates, and updates will
            be kept in memory until they are processed. Note that
            you must set this to at least ``0`` if you want to be
            able to process updates through :meth:`updates.poll()`.

        timeout (`int` | `float` | `timedelta`, optional):
            The timeout to be used when receiving responses from
            the network. Defaults to 5 seconds.

        spawn_read_thread (`bool`, optional):
            Whether to use an extra background thread or not. Defaults
            to ``True`` so receiving items from the network happens
            instantly, as soon as they arrive. Can still be disabled
            if you want to run the library without any additional thread.

        report_errors (`bool`, optional):
            Whether to report RPC errors or not. Defaults to ``True``,
            see :ref:`api-status` for more information.

    Kwargs:
        Some extra parameters are required when establishing the first
        connection. These are are (along with their default values):

            .. code-block:: python

                 device_model     = platform.node()
                 system_version   = platform.system()
                 app_version      = TelegramClient.__version__
                 lang_code        = 'en'
                 system_lang_code = lang_code
    """

    # region Initialization

    def __init__(self, session, api_id, api_hash,
                 *,
                 connection=ConnectionTcpFull,
                 use_ipv6=False,
                 proxy=None,
                 timeout=timedelta(seconds=10),
                 loop=None,
                 report_errors=True,
                 **kwargs):
        super().__init__(
            session, api_id, api_hash,
            connection=connection,
            use_ipv6=use_ipv6,
            proxy=proxy,
            timeout=timeout,
            loop=loop,
            report_errors=report_errors,
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

    async def send_code_request(self, phone, force_sms=False):
        """
        Sends a code request to the specified phone number.

        Args:
            phone (`str` | `int`):
                The phone to which the code will be sent.

            force_sms (`bool`, optional):
                Whether to force sending as SMS.

        Returns:
            An instance of :tl:`SentCode`.
        """
        phone = utils.parse_phone(phone) or self._phone
        phone_hash = self._phone_code_hash.get(phone)

        if not phone_hash:
            result = await self(SendCodeRequest(phone, self.api_id, self.api_hash))
            self._phone_code_hash[phone] = phone_hash = result.phone_code_hash
        else:
            force_sms = True

        self._phone = phone

        if force_sms:
            result = await self(ResendCodeRequest(phone, phone_hash))
            self._phone_code_hash[phone] = result.phone_code_hash

        return result

    async def start(self,
                    phone=lambda: input('Please enter your phone: '),
                    password=lambda: getpass.getpass(
                        'Please enter your password: '),
                    bot_token=None, force_sms=False, code_callback=None,
                    first_name='New User', last_name=''):
        """
        Convenience method to interactively connect and sign in if required,
        also taking into consideration that 2FA may be enabled in the account.

        Example usage:
            >>> client = await TelegramClient(session, api_id, api_hash).start(phone)
            Please enter the code you received: 12345
            Please enter your password: *******
            (You are now logged in)

        Args:
            phone (`str` | `int` | `callable`):
                The phone (or callable without arguments to get it)
                to which the code will be sent.

            password (`callable`, optional):
                The password for 2 Factor Authentication (2FA).
                This is only required if it is enabled in your account.

            bot_token (`str`):
                Bot Token obtained by `@BotFather <https://t.me/BotFather>`_
                to log in as a bot. Cannot be specified with ``phone`` (only
                one of either allowed).

            force_sms (`bool`, optional):
                Whether to force sending the code request as SMS.
                This only makes sense when signing in with a `phone`.

            code_callback (`callable`, optional):
                A callable that will be used to retrieve the Telegram
                login code. Defaults to `input()`.

            first_name (`str`, optional):
                The first name to be used if signing up. This has no
                effect if the account already exists and you sign in.

            last_name (`str`, optional):
                Similar to the first name, but for the last. Optional.

        Returns:
            This `TelegramClient`, so initialization
            can be chained with ``.start()``.
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
            await self.connect()

        if self.is_user_authorized():
            await self._check_events_pending_resolve()
            return self

        if bot_token:
            await self.sign_in(bot_token=bot_token)
            return self

        # Turn the callable into a valid phone number
        while callable(phone):
            phone = utils.parse_phone(phone()) or phone

        me = None
        attempts = 0
        max_attempts = 3
        two_step_detected = False

        sent_code = await self.send_code_request(phone, force_sms=force_sms)
        sign_up = not sent_code.phone_registered
        while attempts < max_attempts:
            try:
                if sign_up:
                    me = await self.sign_up(code_callback(), first_name, last_name)
                else:
                    # Raises SessionPasswordNeededError if 2FA enabled
                    me = await self.sign_in(phone, code_callback())
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
            me = await self.sign_in(phone=phone, password=password)

        # We won't reach here if any step failed (exit by exception)
        signed, name = 'Signed in successfully as', utils.get_display_name(me)
        try:
            print(signed, name)
        except UnicodeEncodeError:
            # Some terminals don't support certain characters
            print(signed, name.encode('utf-8', errors='ignore')
                              .decode('ascii', errors='ignore'))

        await self._check_events_pending_resolve()
        return self

    async def sign_in(self, phone=None, code=None,
                      password=None, bot_token=None, phone_code_hash=None):
        """
        Starts or completes the sign in process with the given phone number
        or code that Telegram sent.

        Args:
            phone (`str` | `int`):
                The phone to send the code to if no code was provided,
                or to override the phone that was previously used with
                these requests.

            code (`str` | `int`):
                The code that Telegram sent. Note that if you have sent this
                code through the application itself it will immediately
                expire. If you want to send the code, obfuscate it somehow.
                If you're not doing any of this you can ignore this note.

            password (`str`):
                2FA password, should be used if a previous call raised
                SessionPasswordNeededError.

            bot_token (`str`):
                Used to sign in as a bot. Not all requests will be available.
                This should be the hash the @BotFather gave you.

            phone_code_hash (`str`):
                The hash returned by .send_code_request. This can be set to None
                to use the last hash known.

        Returns:
            The signed in user, or the information about
            :meth:`send_code_request`.
        """
        if self.is_user_authorized():
            await self._check_events_pending_resolve()
            return self.get_me()

        if phone and not code and not password:
            return await self.send_code_request(phone)
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
            result = await self(SignInRequest(phone, phone_code_hash, str(code)))
        elif password:
            salt = (await self(GetPasswordRequest())).current_salt
            result = await self(CheckPasswordRequest(
                helpers.get_password_hash(password, salt)
            ))
        elif bot_token:
            result = await self(ImportBotAuthorizationRequest(
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
        await self._set_connected_and_authorized()
        return result.user

    async def sign_up(self, code, first_name, last_name=''):
        """
        Signs up to Telegram if you don't have an account yet.
        You must call .send_code_request(phone) first.

        Args:
            code (`str` | `int`):
                The code sent by Telegram

            first_name (`str`):
                The first name to be used by the new account.

            last_name (`str`, optional)
                Optional last name.

        Returns:
            The new created :tl:`User`.
        """
        if self.is_user_authorized():
            await self._check_events_pending_resolve()
            return await self.get_me()

        result = await self(SignUpRequest(
            phone_number=self._phone,
            phone_code_hash=self._phone_code_hash.get(self._phone, ''),
            phone_code=str(code),
            first_name=first_name,
            last_name=last_name
        ))

        self._self_input_peer = utils.get_input_peer(
            result.user, allow_self=False
        )
        await self._set_connected_and_authorized()
        return result.user

    async def log_out(self):
        """
        Logs out Telegram and deletes the current ``*.session`` file.

        Returns:
            ``True`` if the operation was successful.
        """
        try:
            await self(LogOutRequest())
        except RPCError:
            return False

        self.disconnect()
        self.session.delete()
        self._authorized = False
        return True

    async def get_me(self, input_peer=False):
        """
        Gets "me" (the self user) which is currently authenticated,
        or None if the request fails (hence, not authenticated).

        Args:
            input_peer (`bool`, optional):
                Whether to return the :tl:`InputPeerUser` version or the normal
                :tl:`User`. This can be useful if you just need to know the ID
                of yourself.

        Returns:
            Your own :tl:`User`.
        """
        if input_peer and self._self_input_peer:
            return self._self_input_peer
        try:
            me = (await self(GetUsersRequest([InputUserSelf()])))[0]
            if not self._self_input_peer:
                self._self_input_peer = utils.get_input_peer(
                    me, allow_self=False
                )

            return self._self_input_peer if input_peer else me
        except UnauthorizedError:
            return None

    # endregion

    # region Dialogs ("chats") requests

    @async_generator
    async def iter_dialogs(self, limit=None, offset_date=None, offset_id=0,
                           offset_peer=InputPeerEmpty(), _total=None):
        """
        Returns an iterator over the dialogs, yielding 'limit' at most.
        Dialogs are the open "chats" or conversations with other people,
        groups you have joined, or channels you are subscribed to.

        Args:
            limit (`int` | `None`):
                How many dialogs to be retrieved as maximum. Can be set to
                ``None`` to retrieve all dialogs. Note that this may take
                whole minutes if you have hundreds of dialogs, as Telegram
                will tell the library to slow down through a
                ``FloodWaitError``.

            offset_date (`datetime`, optional):
                The offset date to be used.

            offset_id (`int`, optional):
                The message ID to be used as an offset.

            offset_peer (:tl:`InputPeer`, optional):
                The peer to be used as an offset.

            _total (`list`, optional):
                A single-item list to pass the total parameter by reference.

        Yields:
            Instances of `telethon.tl.custom.dialog.Dialog`.
        """
        limit = float('inf') if limit is None else int(limit)
        if limit == 0:
            if not _total:
                return
            # Special case, get a single dialog and determine count
            dialogs = await self(GetDialogsRequest(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=1
            ))
            _total[0] = getattr(dialogs, 'count', len(dialogs.dialogs))
            return

        seen = set()
        req = GetDialogsRequest(
            offset_date=offset_date,
            offset_id=offset_id,
            offset_peer=offset_peer,
            limit=0
        )
        while len(seen) < limit:
            req.limit = min(limit - len(seen), 100)
            r = await self(req)

            if _total:
                _total[0] = getattr(r, 'count', len(r.dialogs))
            messages = {m.id: m for m in r.messages}
            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(r.users, r.chats)}

            # Happens when there are pinned dialogs
            if len(r.dialogs) > limit:
                r.dialogs = r.dialogs[:limit]

            for d in r.dialogs:
                peer_id = utils.get_peer_id(d.peer)
                if peer_id not in seen:
                    seen.add(peer_id)
                    await yield_(Dialog(self, d, entities, messages))

            if len(r.dialogs) < req.limit or not isinstance(r, DialogsSlice):
                # Less than we requested means we reached the end, or
                # we didn't get a DialogsSlice which means we got all.
                break

            req.offset_date = r.messages[-1].date
            req.offset_peer = entities[utils.get_peer_id(r.dialogs[-1].peer)]
            req.offset_id = r.messages[-1].id
            req.exclude_pinned = True

    async def get_dialogs(self, *args, **kwargs):
        """
        Same as :meth:`iter_dialogs`, but returns a list instead
        with an additional ``.total`` attribute on the list.
        """
        total = [0]
        kwargs['_total'] = total
        dialogs = UserList()
        async for dialog in self.iter_dialogs(*args, **kwargs):
            dialogs.append(dialog)
        dialogs.total = total[0]
        return dialogs

    @async_generator
    async def iter_drafts(self):  # TODO: Ability to provide a `filter`
        """
        Iterator over all open draft messages.

        Instances of `telethon.tl.custom.draft.Draft` are yielded.
        You can call `telethon.tl.custom.draft.Draft.set_message`
        to change the message or `telethon.tl.custom.draft.Draft.delete`
        among other things.
        """
        for update in (await self(GetAllDraftsRequest())).updates:
            await yield_(Draft._from_update(self, update))

    async def get_drafts(self):
        """
        Same as :meth:`iter_drafts`, but returns a list instead.
        """
        return list(await self.iter_drafts())

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

    async def _parse_message_text(self, message, parse_mode):
        """
        Returns a (parsed message, entities) tuple depending on ``parse_mode``.
        """
        if not parse_mode:
            return message, []

        if isinstance(parse_mode, str):
            parse_mode = parse_mode.lower()
            if parse_mode in {'md', 'markdown'}:
                message, msg_entities = markdown.parse(message)
            elif parse_mode.startswith('htm'):
                message, msg_entities = html.parse(message)
            else:
                raise ValueError('Unknown parsing mode: {}'.format(parse_mode))
        elif callable(parse_mode):
            message, msg_entities = parse_mode(message)
        else:
            raise TypeError('Invalid parsing mode type: {}'.format(parse_mode))

        for i, e in enumerate(msg_entities):
            if isinstance(e, MessageEntityTextUrl):
                m = re.match(r'^@|\+|tg://user\?id=(\d+)', e.url)
                if m:
                    try:
                        msg_entities[i] = InputMessageEntityMentionName(
                            e.offset, e.length, await self.get_input_entity(
                                int(m.group(1)) if m.group(1) else e.url
                            )
                        )
                    except (ValueError, TypeError):
                        # Make no replacement
                        pass

        return message, msg_entities

    async def send_message(self, entity, message='', reply_to=None,
                           parse_mode='md', link_preview=True, file=None,
                           force_document=False, clear_draft=False):
        """
        Sends the given message to the specified entity (user/chat/channel).

        The default parse mode is the same as the official applications
        (a custom flavour of markdown). ``**bold**, `code` or __italic__``
        are available. In addition you can send ``[links](https://example.com)``
        and ``[mentions](@username)`` (or using IDs like in the Bot API:
        ``[mention](tg://user?id=123456789)``) and ``pre`` blocks with three
        backticks.

        Sending a ``/start`` command with a parameter (like ``?start=data``)
        is also done through this method. Simply send ``'/start data'`` to
        the bot.

        Args:
            entity (`entity`):
                To who will it be sent.

            message (`str` | :tl:`Message`):
                The message to be sent, or another message object to resend.

                The maximum length for a message is 35,000 bytes or 4,096
                characters. Longer messages will not be sliced automatically,
                and you should slice them manually if the text to send is
                longer than said length.

            reply_to (`int` | :tl:`Message`, optional):
                Whether to reply to a message or not. If an integer is provided,
                it should be the ID of the message that it should reply to.

            parse_mode (`str`, optional):
                Can be 'md' or 'markdown' for markdown-like parsing (default),
                or 'htm' or 'html' for HTML-like parsing. If ``None`` or any
                other false-y value is provided, the message will be sent with
                no formatting.

                If a ``callable`` is passed, it should be a function accepting
                a `str` as an input and return as output a tuple consisting
                of ``(parsed message str, [MessageEntity instances])``.

                See :tl:`MessageEntity` for allowed message entities.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`file`, optional):
                Sends a message with a file attached (e.g. a photo,
                video, audio or document). The ``message`` may be empty.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.
                Has no effect when sending a file.

        Returns:
            The sent :tl:`Message`.
        """
        if file is not None:
            return await self.send_file(
                entity, file, caption=message, reply_to=reply_to,
                parse_mode=parse_mode, force_document=force_document
            )
        elif not message:
            raise ValueError(
                'The message cannot be empty unless a file is provided'
            )

        entity = await self.get_input_entity(entity)
        if isinstance(message, Message):
            if (message.media
                    and not isinstance(message.media, MessageMediaWebPage)):
                return await self.send_file(entity, message.media,
                                            caption=message.message,
                                            entities=message.entities)

            if reply_to is not None:
                reply_id = self._get_message_id(reply_to)
            elif utils.get_peer_id(entity) == utils.get_peer_id(message.to_id):
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
                no_webpage=not isinstance(message.media, MessageMediaWebPage),
                clear_draft=clear_draft
            )
            message = message.message
        else:
            message, msg_ent =\
                await self._parse_message_text(message, parse_mode)
            request = SendMessageRequest(
                peer=entity,
                message=message,
                entities=msg_ent,
                no_webpage=not link_preview,
                reply_to_msg_id=self._get_message_id(reply_to),
                clear_draft=clear_draft
            )

        result = await self(request)

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

    async def forward_messages(self, entity, messages, from_peer=None):
        """
        Forwards the given message(s) to the specified entity.

        Args:
            entity (`entity`):
                To which entity the message(s) will be forwarded.

            messages (`list` | `int` | :tl:`Message`):
                The message(s) to forward, or their integer IDs.

            from_peer (`entity`):
                If the given messages are integer IDs and not instances
                of the ``Message`` class, this *must* be specified in
                order for the forward to work.

        Returns:
            The list of forwarded :tl:`Message`, or a single one if a list
            wasn't provided as input.
        """
        single = not utils.is_list_like(messages)
        if single:
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
        result = await self(req)
        random_to_id = {}
        id_to_message = {}
        for update in result.updates:
            if isinstance(update, UpdateMessageID):
                random_to_id[update.random_id] = update.id
            elif isinstance(update, (UpdateNewMessage, UpdateNewChannelMessage)):
                id_to_message[update.message.id] = update.message

        result = [id_to_message[random_to_id[rnd]] for rnd in req.random_id]
        return result[0] if single else result

    async def edit_message(self, entity, message=None, text=None,
                           parse_mode='md', link_preview=True):
        """
        Edits the given message ID (to change its contents or disable preview).

        Args:
            entity (`entity` | :tl:`Message`):
                From which chat to edit the message. This can also be
                the message to be edited, and the entity will be inferred
                from it, so the next parameter will be assumed to be the
                message text.

            message (`int` | :tl:`Message` | `str`):
                The ID of the message (or :tl:`Message` itself) to be edited.
                If the `entity` was a :tl:`Message`, then this message will be
                treated as the new text.

            text (`str`, optional):
                The new text of the message. Does nothing if the `entity`
                was a :tl:`Message`.

            parse_mode (`str`, optional):
                Can be 'md' or 'markdown' for markdown-like parsing (default),
                or 'htm' or 'html' for HTML-like parsing. If ``None`` or any
                other false-y value is provided, the message will be sent with
                no formatting.

            link_preview (`bool`, optional):
                Should the link preview be shown?

        Examples:

            >>> async def main():
            ...     client = await TelegramClient(...).start()
            ...     message = await client.send_message('username', 'hello')
            ...
            ...     await client.edit_message('username', message, 'hello!')
            ...     # or
            ...     await client.edit_message('username', message.id, 'Hello')
            ...     # or
            ...     await client.edit_message(message, 'Hello!')
            ...
            >>> loop = ...
            >>> loop.run_until_complete(main())

        Raises:
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but try editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

        Returns:
            The edited :tl:`Message`.
        """
        if isinstance(entity, Message):
            text = message  # Shift the parameters to the right
            message = entity
            entity = entity.to_id

        text, msg_entities = await self._parse_message_text(text, parse_mode)
        request = EditMessageRequest(
            peer=await self.get_input_entity(entity),
            id=self._get_message_id(message),
            message=text,
            no_webpage=not link_preview,
            entities=msg_entities
        )
        result = await self(request)
        return self._get_response_message(request, result)

    async def delete_messages(self, entity, message_ids, revoke=True):
        """
        Deletes a message from a chat, optionally "for everyone".

        Args:
            entity (`entity`):
                From who the message will be deleted. This can actually
                be ``None`` for normal chats, but **must** be present
                for channels and megagroups.

            message_ids (`list` | `int` | :tl:`Message`):
                The IDs (or ID) or messages to be deleted.

            revoke (`bool`, optional):
                Whether the message should be deleted for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will delete the message for everyone.
                This has no effect on channels or megagroups.

        Returns:
            The :tl:`AffectedMessages`.
        """
        if not utils.is_list_like(message_ids):
            message_ids = (message_ids,)

        message_ids = [
            m.id if isinstance(m, (Message, MessageService, MessageEmpty))
            else int(m) for m in message_ids
        ]

        if entity is None:
            return await self(messages.DeleteMessagesRequest(message_ids, revoke=revoke))

        entity = await self.get_input_entity(entity)

        if isinstance(entity, InputPeerChannel):
            return await self(channels.DeleteMessagesRequest(entity, message_ids))
        else:
            return await self(messages.DeleteMessagesRequest(message_ids, revoke=revoke))

    @async_generator
    async def iter_messages(self, entity, limit=20, offset_date=None,
                            offset_id=0, max_id=0, min_id=0, add_offset=0,
                            search=None, filter=None, from_user=None,
                            batch_size=100, wait_time=None, _total=None):
        """
        Iterator over the message history for the specified entity.

        If either `search`, `filter` or `from_user` are provided,
        :tl:`messages.Search` will be used instead of :tl:`messages.getHistory`.

        Args:
            entity (`entity`):
                The entity from whom to retrieve the message history.

            limit (`int` | `None`, optional):
                Number of messages to be retrieved. Due to limitations with
                the API retrieving more than 3000 messages will take longer
                than half a minute (or even more based on previous calls).
                The limit may also be ``None``, which would eventually return
                the whole history.

            offset_date (`datetime`):
                Offset date (messages *previous* to this date will be
                retrieved). Exclusive.

            offset_id (`int`):
                Offset message ID (only messages *previous* to the given
                ID will be retrieved). Exclusive.

            max_id (`int`):
                All the messages with a higher (newer) ID or equal to this will
                be excluded

            min_id (`int`):
                All the messages with a lower (older) ID or equal to this will
                be excluded.

            add_offset (`int`):
                Additional message offset (all of the specified offsets +
                this offset = older messages).

            search (`str`):
                The string to be used as a search query.

            filter (:tl:`MessagesFilter` | `type`):
                The filter to use when returning messages. For instance,
                :tl:`InputMessagesFilterPhotos` would yield only messages
                containing photos.

            from_user (`entity`):
                Only messages from this user will be returned.

            batch_size (`int`):
                Messages will be returned in chunks of this size (100 is
                the maximum). While it makes no sense to modify this value,
                you are still free to do so.

            wait_time (`int`):
                Wait time between different :tl:`GetHistoryRequest`. Use this
                parameter to avoid hitting the ``FloodWaitError`` as needed.
                If left to ``None``, it will default to 1 second only if
                the limit is higher than 3000.

            _total (`list`, optional):
                A single-item list to pass the total parameter by reference.

        Yields:
            Instances of :tl:`Message` with extra attributes:

                * ``.sender`` = entity of the sender.
                * ``.fwd_from.sender`` = if fwd_from, who sent it originally.
                * ``.fwd_from.channel`` = if fwd_from, original channel.
                * ``.to`` = entity to which the message was sent.

        Notes:
            Telegram's flood wait limit for :tl:`GetHistoryRequest` seems to
            be around 30 seconds per 3000 messages, therefore a sleep of 1
            second is the default for this limit (or above). You may need
            an higher limit, so you're free to set the ``batch_size`` that
            you think may be good.
        """
        entity = await self.get_input_entity(entity)
        limit = float('inf') if limit is None else int(limit)
        if search is not None or filter or from_user:
            if filter is None:
                filter = InputMessagesFilterEmpty()
            request = SearchRequest(
                peer=entity,
                q=search or '',
                filter=filter() if isinstance(filter, type) else filter,
                min_date=None,
                max_date=offset_date,
                offset_id=offset_id,
                add_offset=add_offset,
                limit=1,
                max_id=max_id,
                min_id=min_id,
                hash=0,
                from_id=self.get_input_entity(from_user) if from_user else None
            )
        else:
            request = GetHistoryRequest(
                peer=entity,
                limit=1,
                offset_date=offset_date,
                offset_id=offset_id,
                min_id=min_id,
                max_id=max_id,
                add_offset=add_offset,
                hash=0
            )

        if limit == 0:
            if not _total:
                return
            # No messages, but we still need to know the total message count
            result = await self(request)
            _total[0] = getattr(result, 'count', len(result.messages))
            return

        if wait_time is None:
            wait_time = 1 if limit > 3000 else 0

        have = 0
        last_id = float('inf')
        batch_size = min(max(batch_size, 1), 100)
        while have < limit:
            start = time.time()
            # Telegram has a hard limit of 100
            request.limit = min(limit - have, batch_size)
            r = await self(request)
            if _total:
                _total[0] = getattr(r, 'count', len(r.messages))

            entities = {utils.get_peer_id(x): x
                        for x in itertools.chain(r.users, r.chats)}

            for message in r.messages:
                if isinstance(message, MessageEmpty) or message.id >= last_id:
                    continue

                # There has been reports that on bad connections this method
                # was returning duplicated IDs sometimes. Using ``last_id``
                # is an attempt to avoid these duplicates, since the message
                # IDs are returned in descending order.
                last_id = message.id

                # Add a few extra attributes to the Message to be friendlier.
                # To make messages more friendly, always add message
                # to service messages, and action to normal messages.
                message.message = getattr(message, 'message', None)
                message.action = getattr(message, 'action', None)
                message.to = entities[utils.get_peer_id(message.to_id)]
                message.sender = (
                    None if not message.from_id else
                    entities[utils.get_peer_id(message.from_id)]
                )
                if getattr(message, 'fwd_from', None):
                    message.fwd_from.sender = (
                        None if not message.fwd_from.from_id else
                        entities[utils.get_peer_id(message.fwd_from.from_id)]
                    )
                    message.fwd_from.channel = (
                        None if not message.fwd_from.channel_id else
                        entities[utils.get_peer_id(
                            PeerChannel(message.fwd_from.channel_id)
                        )]
                    )
                await yield_(message)
                have += 1

            if len(r.messages) < request.limit:
                break

            request.offset_id = r.messages[-1].id
            if isinstance(request, GetHistoryRequest):
                request.offset_date = r.messages[-1].date
            else:
                request.max_date = r.messages[-1].date

            await asyncio.sleep(max(wait_time - (time.time() - start), 0))

    async def get_messages(self, *args, **kwargs):
        """
        Same as :meth:`iter_messages`, but returns a list instead
        with an additional ``.total`` attribute on the list.
        """
        total = [0]
        kwargs['_total'] = total
        msgs = UserList()
        async for msg in self.iter_messages(*args, **kwargs):
            msgs.append(msg)

        msgs.total = total[0]
        return msgs

    async def get_message_history(self, *args, **kwargs):
        """Deprecated, see :meth:`get_messages`."""
        warnings.warn(
            'get_message_history is deprecated, use get_messages instead'
        )
        return await self.get_messages(*args, **kwargs)

    async def send_read_acknowledge(self, entity, message=None, max_id=None,
                                    clear_mentions=False):
        """
        Sends a "read acknowledge" (i.e., notifying the given peer that we've
        read their messages, also known as the "double check").

        This effectively marks a message as read (or more than one) in the
        given conversation.

        Args:
            entity (`entity`):
                The chat where these messages are located.

            message (`list` | :tl:`Message`):
                Either a list of messages or a single message.

            max_id (`int`):
                Overrides messages, until which message should the
                acknowledge should be sent.

            clear_mentions (`bool`):
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

        entity = await self.get_input_entity(entity)
        if clear_mentions:
            await self(ReadMentionsRequest(entity))
            if max_id is None:
                return True

        if max_id is not None:
            if isinstance(entity, InputPeerChannel):
                return await self(channels.ReadHistoryRequest(entity, max_id=max_id))
            else:
                return await self(messages.ReadHistoryRequest(entity, max_id=max_id))

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

    @async_generator
    async def iter_participants(self, entity, limit=None, search='',
                                filter=None, aggressive=False, _total=None):
        """
        Iterator over the participants belonging to the specified chat.

        Args:
            entity (`entity`):
                The entity from which to retrieve the participants list.

            limit (`int`):
                Limits amount of participants fetched.

            search (`str`, optional):
                Look for participants with this string in name/username.

            filter (:tl:`ChannelParticipantsFilter`, optional):
                The filter to be used, if you want e.g. only admins
                Note that you might not have permissions for some filter.
                This has no effect for normal chats or users.

            aggressive (`bool`, optional):
                Aggressively looks for all participants in the chat in
                order to get more than 10,000 members (a hard limit
                imposed by Telegram). Note that this might take a long
                time (over 5 minutes), but is able to return over 90,000
                participants on groups with 100,000 members.

                This has no effect for groups or channels with less than
                10,000 members, or if a ``filter`` is given.

            _total (`list`, optional):
                A single-item list to pass the total parameter by reference.

        Yields:
            The :tl:`User` objects returned by :tl:`GetParticipantsRequest`
            with an additional ``.participant`` attribute which is the
            matched :tl:`ChannelParticipant` type for channels/megagroups
            or :tl:`ChatParticipants` for normal chats.
        """
        if isinstance(filter, type):
            if filter in (ChannelParticipantsBanned, ChannelParticipantsKicked,
                          ChannelParticipantsSearch):
                # These require a `q` parameter (support types for convenience)
                filter = filter('')
            else:
                filter = filter()

        entity = await self.get_input_entity(entity)
        if search and (filter or not isinstance(entity, InputPeerChannel)):
            # We need to 'search' ourselves unless we have a PeerChannel
            search = search.lower()

            def filter_entity(ent):
                return search in utils.get_display_name(ent).lower() or\
                       search in (getattr(ent, 'username', '') or None).lower()
        else:
            def filter_entity(ent):
                return True

        limit = float('inf') if limit is None else int(limit)
        if isinstance(entity, InputPeerChannel):
            if _total or (aggressive and not filter):
                total = (await self(GetFullChannelRequest(
                    entity
                ))).full_chat.participants_count
                if _total:
                    _total[0] = total
            else:
                total = 0

            if limit == 0:
                return

            seen = set()
            if total > 10000 and aggressive and not filter:
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
                    filter=filter or ChannelParticipantsSearch(search),
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

                results = await self(requests)
                for i in reversed(range(len(requests))):
                    participants = results[i]
                    if not participants.users:
                        requests.pop(i)
                    else:
                        requests[i].offset += len(participants.participants)
                        users = {user.id: user for user in participants.users}
                        for participant in participants.participants:
                            user = users[participant.user_id]
                            if not filter_entity(user) or user.id in seen:
                                continue

                            seen.add(participant.user_id)
                            user = users[participant.user_id]
                            user.participant = participant
                            await yield_(user)
                            if len(seen) >= limit:
                                return

        elif isinstance(entity, InputPeerChat):
            # TODO We *could* apply the `filter` here ourselves
            full = await self(GetFullChatRequest(entity.chat_id))
            if not isinstance(full.full_chat.participants, ChatParticipants):
                # ChatParticipantsForbidden won't have ``.participants``
                _total[0] = 0
                return

            if _total:
                _total[0] = len(full.full_chat.participants.participants)

            have = 0
            users = {user.id: user for user in full.users}
            for participant in full.full_chat.participants.participants:
                user = users[participant.user_id]
                if not filter_entity(user):
                    continue
                have += 1
                if have > limit:
                    break
                else:
                    user = users[participant.user_id]
                    user.participant = participant
                    await yield_(user)
        else:
            if _total:
                _total[0] = 1
            if limit != 0:
                user = await self.get_entity(entity)
                if filter_entity(user):
                    user.participant = None
                    await yield_(user)

    async def get_participants(self, *args, **kwargs):
        """
        Same as :meth:`iter_participants`, but returns a list instead
        with an additional ``.total`` attribute on the list.
        """
        total = [0]
        kwargs['_total'] = total
        participants = UserList()
        async for participant in self.iter_participants(*args, **kwargs):
            participants.append(participant)
        participants.total = total[0]
        return participants

    # endregion

    # region Uploading files

    async def send_file(self, entity, file, caption='',
                        force_document=False, progress_callback=None,
                        reply_to=None,
                        attributes=None,
                        thumb=None,
                        allow_cache=True,
                        parse_mode='md',
                        voice_note=False,
                        video_note=False,
                        **kwargs):
        """
        Sends a file to the specified entity.

        Args:
            entity (`entity`):
                Who will receive the file.

            file (`str` | `bytes` | `file` | `media`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

                Furthermore the file may be any media (a message, document,
                photo or similar) so that it can be resent without the need
                to download and re-upload it again.

                If a list or similar is provided, the files in it will be
                sent as an album in the order in which they appear, sliced
                in chunks of 10 if more than 10 are given.

            caption (`str`, optional):
                Optional caption for the sent media message.

            force_document (`bool`, optional):
                If left to ``False`` and the file is a path that ends with
                the extension of an image file or a video file, it will be
                sent as such. Otherwise always as a document.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

            reply_to (`int` | :tl:`Message`):
                Same as `reply_to` from `send_message`.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            thumb (`str` | `bytes` | `file`, optional):
                Optional thumbnail (for videos).

            allow_cache (`bool`, optional):
                Whether to allow using the cached version stored in the
                database or not. Defaults to ``True`` to avoid re-uploads.
                Must be ``False`` if you wish to use different attributes
                or thumb than those that were used when the file was cached.

            parse_mode (`str`, optional):
                The parse mode for the caption message.

            voice_note (`bool`, optional):
                If ``True`` the audio will be sent as a voice note.

                Set `allow_cache` to ``False`` if you sent the same file
                without this setting before for it to work.

            video_note (`bool`, optional):
                If ``True`` the video will be sent as a video note,
                also known as a round video message.

                Set `allow_cache` to ``False`` if you sent the same file
                without this setting before for it to work.

        Notes:
            If the ``hachoir3`` package (``hachoir`` module) is installed,
            it will be used to determine metadata from audio and video files.

        Returns:
            The :tl:`Message` (or messages) containing the sent file,
            or messages if a list of them was passed.
        """
        # First check if the user passed an iterable, in which case
        # we may want to send as an album if all are photo files.
        if utils.is_list_like(file):
            # TODO Fix progress_callback
            images = []
            if force_document:
                documents = file
            else:
                documents = []
                for x in file:
                    if utils.is_image(x):
                        images.append(x)
                    else:
                        documents.append(x)

            result = []
            while images:
                result += await self._send_album(
                    entity, images[:10], caption=caption,
                    progress_callback=progress_callback, reply_to=reply_to,
                    parse_mode=parse_mode
                )
                images = images[10:]

            for x in documents:
                result.append(await self.send_file(
                    entity, x, allow_cache=allow_cache,
                    caption=caption, force_document=force_document,
                    progress_callback=progress_callback, reply_to=reply_to,
                    attributes=attributes, thumb=thumb, voice_note=voice_note,
                    video_note=video_note, **kwargs
                ))
            return result

        entity = await self.get_input_entity(entity)
        reply_to = self._get_message_id(reply_to)

        # Not document since it's subject to change.
        # Needed when a Message is passed to send_message and it has media.
        if 'entities' in kwargs:
            msg_entities = kwargs['entities']
        else:
            caption, msg_entities =\
                await self._parse_message_text(caption, parse_mode)

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
                return self._get_response_message(request, await self(request))

        as_image = utils.is_image(file) and not force_document
        use_cache = InputPhoto if as_image else InputDocument
        file_handle = await self.upload_file(
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
                        voice=voice_note,
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
                            round_message=video_note,
                            w=m.get('width') if m.has('width') else 0,
                            h=m.get('height') if m.has('height') else 0,
                            duration=int(m.get('duration').seconds
                                         if m.has('duration') else 0)
                        )
                    else:
                        doc = DocumentAttributeVideo(0, 0, 0,
                                                     round_message=video_note)

                    attr_dict[DocumentAttributeVideo] = doc
            else:
                attr_dict = {
                    DocumentAttributeFilename: DocumentAttributeFilename(
                        os.path.basename(
                            getattr(file, 'name', None) or 'unnamed'))
                }

            if voice_note:
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
                input_kw['thumb'] = await self.upload_file(thumb)

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
        msg = self._get_response_message(request, await self(request))
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
        """Deprecated, see :meth:`send_file`."""
        warnings.warn('send_voice_note is deprecated, use '
                      'send_file(..., voice_note=True) instead')
        kwargs['is_voice_note'] = True
        return self.send_file(*args, **kwargs)

    async def _send_album(self, entity, files, caption='',
                          progress_callback=None, reply_to=None,
                          parse_mode='md'):
        """Specialized version of .send_file for albums"""
        # We don't care if the user wants to avoid cache, we will use it
        # anyway. Why? The cached version will be exactly the same thing
        # we need to produce right now to send albums (uploadMedia), and
        # cache only makes a difference for documents where the user may
        # want the attributes used on them to change.
        #
        # In theory documents can be sent inside the albums but they appear
        # as different messages (not inside the album), and the logic to set
        # the attributes/avoid cache is already written in .send_file().
        entity = await self.get_input_entity(entity)
        if not utils.is_list_like(caption):
            caption = (caption,)

        captions = []
        for caption in reversed(caption):  # Pop from the end (so reverse)
            captions.append(await self._parse_message_text(caption or '',
                                                           parse_mode))

        reply_to = self._get_message_id(reply_to)

        # Need to upload the media first, but only if they're not cached yet
        media = []
        for file in files:
            # fh will either be InputPhoto or a modified InputFile
            fh = await self.upload_file(file, use_cache=InputPhoto)
            if not isinstance(fh, InputPhoto):
                input_photo = utils.get_input_photo((await self(UploadMediaRequest(
                    entity, media=InputMediaUploadedPhoto(fh)
                ))).photo)
                self.session.cache_file(fh.md5, fh.size, input_photo)
                fh = input_photo

            if captions:
                caption, msg_entities = captions.pop()
            else:
                caption, msg_entities = '', None
            media.append(InputSingleMedia(InputMediaPhoto(fh), message=caption,
                                          entities=msg_entities))

        # Now we can construct the multi-media request
        result = await self(SendMultiMediaRequest(
            entity, reply_to_msg_id=reply_to, multi_media=media
        ))
        return [
            self._get_response_message(update.id, result)
            for update in result.updates
            if isinstance(update, UpdateMessageID)
        ]

    async def upload_file(self, file, part_size_kb=None, file_name=None,
                          use_cache=None, progress_callback=None):
        """
        Uploads the specified file and returns a handle (an instance of
        :tl:`InputFile` or :tl:`InputFileBig`, as required) which can be
        later used before it expires (they are usable during less than a day).

        Uploading a file will simply return a "handle" to the file stored
        remotely in the Telegram servers, which can be later used on. This
        will **not** upload the file to your own chat or any chat at all.

        Args:
            file (`str` | `bytes` | `file`):
                The path of the file, byte array, or stream that will be sent.
                Note that if a byte array or a stream is given, a filename
                or its type won't be inferred, and it will be sent as an
                "unnamed application/octet-stream".

            part_size_kb (`int`, optional):
                Chunk size when uploading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_name (`str`, optional):
                The file name which will be used on the resulting InputFile.
                If not specified, the name will be taken from the ``file``
                and if this is not a ``str``, it will be ``"unnamed"``.

            use_cache (`type`, optional):
                The type of cache to use (currently either :tl:`InputDocument`
                or :tl:`InputPhoto`). If present and the file is small enough
                to need the MD5, it will be checked against the database,
                and if a match is found, the upload won't be made. Instead,
                an instance of type ``use_cache`` will be returned.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

        Returns:
            :tl:`InputFileBig` if the file size is larger than 10MB,
            `telethon.tl.custom.input_sized_file.InputSizedFile`
            (subclass of :tl:`InputFile`) otherwise.
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

                result = await self(request)
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

    async def download_profile_photo(self, entity, file=None, download_big=True):
        """
        Downloads the profile photo of the given entity (user/chat/channel).

        Args:
            entity (`entity`):
                From who the photo will be downloaded.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

            download_big (`bool`, optional):
                Whether to use the big version of the available photos.

        Returns:
            ``None`` if no photo was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.
        """
        # hex(crc32(x.encode('ascii'))) for x in
        # ('User', 'Chat', 'UserFull', 'ChatFull')
        ENTITIES = (0x2da17977, 0xc5af5d94, 0x1f4661b9, 0xd49a2697)
        # ('InputPeer', 'InputUser', 'InputChannel')
        INPUTS = (0xc91c90b6, 0xe669bf46, 0x40f202fd)
        if not isinstance(entity, TLObject) or entity.SUBCLASS_OF_ID in INPUTS:
            entity = await self.get_entity(entity)

        possible_names = []
        if entity.SUBCLASS_OF_ID not in ENTITIES:
            photo = entity
        else:
            if not hasattr(entity, 'photo'):
                # Special case: may be a ChatFull with photo:Photo
                # This is different from a normal UserProfilePhoto and Chat
                if not hasattr(entity, 'chat_photo'):
                    return None

                return await self._download_photo(
                    entity.chat_photo, file, date=None, progress_callback=None)

            for attr in ('username', 'first_name', 'title'):
                possible_names.append(getattr(entity, attr, None))

            photo = entity.photo

        if isinstance(photo, (UserProfilePhoto, ChatPhoto)):
            loc = photo.photo_big if download_big else photo.photo_small
        else:
            try:
                loc = utils.get_input_location(photo)
            except TypeError:
                return None

        file = self._get_proper_filename(
            file, 'profile_photo', '.jpg',
            possible_names=possible_names
        )

        try:
            await self.download_file(loc, file)
            return file
        except LocationInvalidError:
            # See issue #500, Android app fails as of v4.6.0 (1155).
            # The fix seems to be using the full channel chat photo.
            ie = await self.get_input_entity(entity)
            if isinstance(ie, InputPeerChannel):
                full = await self(GetFullChannelRequest(ie))
                return await self._download_photo(
                    full.full_chat.chat_photo, file,
                    date=None, progress_callback=None
                )
            else:
                # Until there's a report for chats, no need to.
                return None

    async def download_media(self, message, file=None, progress_callback=None):
        """
        Downloads the given media, or the media from a specified Message.

        Note that if the download is too slow, you should consider installing
        ``cryptg`` (through ``pip install cryptg``) so that decrypting the
        received data is done in C instead of Python (much faster).

        message (:tl:`Message` | :tl:`Media`):
            The media or message containing the media that will be downloaded.

        file (`str` | `file`, optional):
            The output file path, directory, or stream-like object.
            If the path exists and is a file, it will be overwritten.

        progress_callback (`callable`, optional):
            A callback function accepting two parameters:
            ``(received bytes, total)``.

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

        if isinstance(media, MessageMediaWebPage):
            if isinstance(media.webpage, WebPage):
                media = media.webpage.document or media.webpage.photo

        if isinstance(media, (MessageMediaPhoto, Photo,
                              PhotoSize, PhotoCachedSize)):
            return await self._download_photo(
                media, file, date, progress_callback
            )
        elif isinstance(media, (MessageMediaDocument, Document)):
            return await self._download_document(
                media, file, date, progress_callback
            )
        elif isinstance(media, MessageMediaContact):
            return await self._download_contact(
                media, file
            )

    async def _download_photo(self, photo, file, date, progress_callback):
        """Specialized version of .download_media() for photos"""
        # Determine the photo and its largest size
        if isinstance(photo, MessageMediaPhoto):
            photo = photo.photo
        if isinstance(photo, Photo):
            for size in reversed(photo.sizes):
                if not isinstance(size, PhotoSizeEmpty):
                    photo = size
                    break
            else:
                return
        if not isinstance(photo, (PhotoSize, PhotoCachedSize)):
            return

        file = self._get_proper_filename(file, 'photo', '.jpg', date=date)
        if isinstance(photo, PhotoCachedSize):
            # No need to download anything, simply write the bytes
            if isinstance(file, str):
                helpers.ensure_parent_dir_exists(file)
                f = open(file, 'wb')
            else:
                f = file
            try:
                f.write(photo.bytes)
            finally:
                if isinstance(file, str):
                    f.close()
            return file

        await self.download_file(photo.location, file, file_size=photo.size,
                                 progress_callback=progress_callback)
        return file

    async def _download_document(self, document, file, date, progress_callback):
        """Specialized version of .download_media() for documents."""
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

        await self.download_file(document, file, file_size=file_size,
                                 progress_callback=progress_callback)
        return file

    @staticmethod
    def _download_contact(mm_contact, file):
        """Specialized version of .download_media() for contacts.
           Will make use of the vCard 4.0 format.
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

    async def download_file(self, input_location, file=None, part_size_kb=None,
                            file_size=None, progress_callback=None):
        """
        Downloads the given input location to a file.

        Args:
            input_location (:tl:`FileLocation` | :tl:`InputFileLocation`):
                The file location from which the file will be downloaded.
                See `telethon.utils.get_input_location` source for a complete
                list of supported types.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.

                If the file path is ``None``, then the result will be
                saved in memory and returned as `bytes`.

            part_size_kb (`int`, optional):
                Chunk size when downloading files. The larger, the less
                requests will be made (up to 512KB maximum).

            file_size (`int`, optional):
                The file size that is about to be downloaded, if known.
                Only used if ``progress_callback`` is specified.

            progress_callback (`callable`, optional):
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

        in_memory = file is None
        if in_memory:
            f = io.BytesIO()
        elif isinstance(file, str):
            # Ensure that we'll be able to download the media
            helpers.ensure_parent_dir_exists(file)
            f = open(file, 'wb')
        else:
            f = file

        # The used client will change if FileMigrateError occurs
        client = self
        cdn_decrypter = None
        input_location = utils.get_input_location(input_location)

        __log__.info('Downloading file in chunks of %d bytes', part_size)
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
                            __log__.info('File lives in a CDN')
                            cdn_decrypter, result = \
                                await CdnDecrypter.prepare_decrypter(
                                    client,
                                    await self._get_cdn_client(result),
                                    result
                                )

                except FileMigrateError as e:
                    __log__.info('File lives in another DC')
                    client = await self._get_exported_client(e.new_dc)
                    continue

                offset += part_size

                # If we have received no data (0 bytes), the file is over
                # So there is nothing left to download and write
                if not result.bytes:
                    # Return some extra information, unless it's a CDN file
                    if in_memory:
                        f.flush()
                        return f.getvalue()
                    else:
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
            if isinstance(file, str) or in_memory:
                f.close()

    # endregion

    # endregion

    # region Event handling

    def on(self, event):
        """
        Decorator helper method around add_event_handler().

        Args:
            event (`_EventBuilder` | `type`):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.
        """
        def decorator(f):
            if self._loop.is_running():
                asyncio.ensure_future(self.add_event_handler(f, event))
            else:
                self._loop.run_until_complete(self.add_event_handler(f, event))
            return f

        return decorator

    async def _check_events_pending_resolve(self):
        if self._events_pending_resolve:
            for event in self._events_pending_resolve:
                await event.resolve(self)
            self._events_pending_resolve.clear()

    async def _on_handler(self, update):
        for builder, callback in self._event_builders:
            event = builder.build(update)
            if event:
                event._client = self
                event.original_update = update
                try:
                    await callback(event)
                except events.StopPropagation:
                    __log__.debug(
                        "Event handler '{}' stopped chain of "
                        "propagation for event {}."
                        .format(callback.__name__, type(event).__name__)
                    )
                    break

    async def add_event_handler(self, callback, event=None):
        """
        Registers the given callback to be called on the specified event.

        Args:
            callback (`callable`):
                The callable function accepting one parameter to be used.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, `telethon.events.raw.Raw` (the
                :tl:`Update` objects with no further processing) will
                be passed instead.
        """

        self.updates.handler = self._on_handler
        if isinstance(event, type):
            event = event()
        elif not event:
            event = events.Raw()

        if self.is_user_authorized():
            await event.resolve(self)
            await self._check_events_pending_resolve()
        else:
            self._events_pending_resolve.append(event)

        self._event_builders.append((event, callback))

    def remove_event_handler(self, callback, event=None):
        """
        Inverse operation of :meth:`add_event_handler`.

        If no event is given, all events for this callback are removed.
        Returns how many callbacks were removed.
        """
        found = 0
        if event and not isinstance(event, type):
            event = type(event)

        i = len(self._event_builders)
        while i:
            i -= 1
            ev, cb = self._event_builders[i]
            if cb == callback and (not event or isinstance(ev, event)):
                del self._event_builders[i]
                found += 1

        return found

    def list_event_handlers(self):
        """
        Lists all added event handlers, returning a list of pairs
        consisting of (callback, event).
        """
        return [(callback, event) for event, callback in self._event_builders]

    async def add_update_handler(self, handler):
        """Deprecated, see :meth:`add_event_handler`."""
        warnings.warn(
            'add_update_handler is deprecated, use the @client.on syntax '
            'or add_event_handler(callback, events.Raw) instead (see '
            'https://telethon.rtfd.io/en/latest/extra/basic/working-'
            'with-updates.html)'
        )
        return await self.add_event_handler(handler, events.Raw)

    def remove_update_handler(self, handler):
        return self.remove_event_handler(handler)

    def list_update_handlers(self):
        return [callback for callback, _ in self.list_event_handlers()]

    async def catch_up(self):
        state = self.session.get_update_state(0)
        if not state:
            return

        self.session.catching_up = True
        try:
            while True:
                d = await self(GetDifferenceRequest(state.pts, state.date, state.qts))
                if isinstance(d, DifferenceEmpty):
                    state.date = d.date
                    state.seq = d.seq
                    break
                elif isinstance(d, (DifferenceSlice, Difference)):
                    if isinstance(d, Difference):
                        state = d.state
                    elif d.intermediate_state.pts > state.pts:
                        state = d.intermediate_state
                    else:
                        # TODO Figure out why other applications can rely on
                        # using always the intermediate_state to eventually
                        # reach a DifferenceEmpty, but that leads to an
                        # infinite loop here (so check against old pts to stop)
                        break

                    self.updates.process(Updates(
                        users=d.users,
                        chats=d.chats,
                        date=state.date,
                        seq=state.seq,
                        updates=d.other_updates + [UpdateNewMessage(m, 0, 0)
                                                   for m in d.new_messages]
                    ))
                elif isinstance(d, DifferenceTooLong):
                    break
        finally:
            self.session.set_update_state(0, state)
            self.session.catching_up = False

    # endregion

    # region Small utilities to make users' life easier

    async def _set_connected_and_authorized(self):
        await super()._set_connected_and_authorized()
        await self._check_events_pending_resolve()

    async def get_entity(self, entity):
        """
        Turns the given entity into a valid Telegram user or chat.

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
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
            :tl:`User`, :tl:`Chat` or :tl:`Channel` corresponding to the
            input entity. A list will be returned if more than one was given.
        """
        single = not utils.is_list_like(entity)
        if single:
            entity = (entity,)

        # Group input entities by string (resolve username),
        # input users (get users), input chat (get chats) and
        # input channels (get channels) to get the most entities
        # in the less amount of calls possible.
        inputs = []
        for x in entity:
            inputs.append(x if isinstance(x, str)
                          else await self.get_input_entity(x))

        users = [x for x in inputs
                 if isinstance(x, (InputPeerUser, InputPeerSelf))]
        chats = [x.chat_id for x in inputs if isinstance(x, InputPeerChat)]
        channels = [x for x in inputs if isinstance(x, InputPeerChannel)]
        if users:
            # GetUsersRequest has a limit of 200 per call
            tmp = []
            while users:
                curr, users = users[:200], users[200:]
                tmp.extend(await self(GetUsersRequest(curr)))
            users = tmp
        if chats:  # TODO Handle chats slice?
            chats = (await self(GetChatsRequest(chats))).chats
        if channels:
            channels = (await self(GetChannelsRequest(channels))).chats

        # Merge users, chats and channels into a single dictionary
        id_entity = {
            utils.get_peer_id(x): x
            for x in itertools.chain(users, chats, channels)
        }

        # We could check saved usernames and put them into the users,
        # chats and channels list from before. While this would reduce
        # the amount of ResolveUsername calls, it would fail to catch
        # username changes.
        result = []
        for x in inputs:
            if isinstance(x, str):
                result.append(await self._get_entity_from_string(x))
            elif not isinstance(x, InputPeerSelf):
                result.append(id_entity[utils.get_peer_id(x)])
            else:
                result.append(next(u for u in id_entity.values()
                                   if isinstance(u, User) and u.is_self))

        return result[0] if single else result

    async def _get_entity_from_string(self, string):
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
            for user in (await self(GetContactsRequest(0))).users:
                if user.phone == phone:
                    return user
        else:
            username, is_join_chat = utils.parse_username(string)
            if is_join_chat:
                invite = await self(CheckChatInviteRequest(username))
                if isinstance(invite, ChatInvite):
                    raise ValueError(
                        'Cannot get entity from a channel (or group) '
                        'that you are not part of. Join the group and retry'
                    )
                elif isinstance(invite, ChatInviteAlready):
                    return invite.chat
            elif username:
                if username in ('me', 'self'):
                    return await self.get_me()

                try:
                    result = await self(ResolveUsernameRequest(username))
                except UsernameNotOccupiedError as e:
                    raise ValueError('No user has "{}" as username'
                                     .format(username)) from e

                for entity in itertools.chain(result.users, result.chats):
                    if getattr(entity, 'username', None) or ''\
                            .lower() == username:
                        return entity
            try:
                # Nobody with this username, maybe it's an exact name/title
                return await self.get_entity(
                    self.session.get_input_entity(string))
            except ValueError:
                pass

        raise ValueError(
            'Cannot find any entity corresponding to "{}"'.format(string)
        )

    async def get_input_entity(self, peer):
        """
        Turns the given peer into its input entity version. Most requests
        use this kind of InputUser, InputChat and so on, so this is the
        most suitable call to make for those cases.

        entity (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
            The integer ID of an user or otherwise either of a
            :tl:`PeerUser`, :tl:`PeerChat` or :tl:`PeerChannel`, for
            which to get its ``Input*`` version.
            If this ``Peer`` hasn't been seen before by the library, the top
            dialogs will be loaded and their entities saved to the session
            file (unless this feature was disabled explicitly).
            If in the end the access hash required for the peer was not found,
            a ValueError will be raised.
        Returns:
            :tl:`InputPeerUser`, :tl:`InputPeerChat` or :tl:`InputPeerChannel`
            or :tl:`InputPeerSelf` if the parameter is ``'me'`` or ``'self'``.

            If you need to get the ID of yourself, you should use
            `get_me` with ``input_peer=True``) instead.
        """
        if peer in ('me', 'self'):
            return InputPeerSelf()

        try:
            # First try to get the entity from cache, otherwise figure it out
            return self.session.get_input_entity(peer)
        except ValueError:
            pass

        if isinstance(peer, str):
            return utils.get_input_peer(await self._get_entity_from_string(peer))

        if not isinstance(peer, int) and (not isinstance(peer, TLObject)
                                          or peer.SUBCLASS_OF_ID != 0x2d45687):
            # Try casting the object into an input peer. Might TypeError.
            # Don't do it if a not-found ID was given (instead ValueError).
            # Also ignore Peer (0x2d45687 == crc32(b'Peer'))'s, lacking hash.
            return utils.get_input_peer(peer)

        raise ValueError(
            'Could not find the input entity for "{}". Please read https://'
            'telethon.readthedocs.io/en/latest/extra/basic/entities.html to'
            ' find out more details.'
            .format(peer)
        )

    async def edit_2fa(self, current_password=None, new_password=None, hint='',
                       email=None):
        """
        Changes the 2FA settings of the logged in user, according to the
        passed parameters. Take note of the parameter explanations.

        Has no effect if both current and new password are omitted.

        current_password (`str`, optional):
            The current password, to authorize changing to ``new_password``.
            Must be set if changing existing 2FA settings.
            Must **not** be set if 2FA is currently disabled.
            Passing this by itself will remove 2FA (if correct).

        new_password (`str`, optional):
            The password to set as 2FA.
            If 2FA was already enabled, ``current_password`` **must** be set.
            Leaving this blank or ``None`` will remove the password.

        hint (`str`, optional):
            Hint to be displayed by Telegram when it asks for 2FA.
            Leaving unspecified is highly discouraged.
            Has no effect if ``new_password`` is not set.

        email (`str`, optional):
            Recovery and verification email. Raises ``EmailUnconfirmedError``
            if value differs from current one, and has no effect if
            ``new_password`` is not set.

        Returns:
            ``True`` if successful, ``False`` otherwise.
        """
        if new_password is None and current_password is None:
            return False

        pass_result = await self(GetPasswordRequest())
        if isinstance(pass_result, NoPassword) and current_password:
            current_password = None

        salt_random = os.urandom(8)
        salt = pass_result.new_salt + salt_random
        if not current_password:
            current_password_hash = salt
        else:
            current_password = pass_result.current_salt +\
                current_password.encode() + pass_result.current_salt
            current_password_hash = hashlib.sha256(current_password).digest()

        if new_password:  # Setting new password
            new_password = salt + new_password.encode('utf-8') + salt
            new_password_hash = hashlib.sha256(new_password).digest()
            new_settings = PasswordInputSettings(
                new_salt=salt,
                new_password_hash=new_password_hash,
                hint=hint
            )
            if email:  # If enabling 2FA or changing email
                new_settings.email = email  # TG counts empty string as None
            return await self(UpdatePasswordSettingsRequest(
                current_password_hash, new_settings=new_settings
            ))
        else:  # Removing existing password
            return await self(UpdatePasswordSettingsRequest(
                current_password_hash,
                new_settings=PasswordInputSettings(
                    new_salt=bytes(),
                    new_password_hash=bytes(),
                    hint=hint
                )
            ))

    # endregion
