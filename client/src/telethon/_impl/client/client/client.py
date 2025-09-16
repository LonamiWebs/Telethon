import asyncio
import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Optional, Sequence, Type, TypeVar

from typing_extensions import Self

from ....version import __version__ as default_version
from ...mtsender import Connector, Sender
from ...mtsender.reconnection import ReconnectionPolicy
from ...session import (
    ChannelRef,
    ChatHashCache,
    DataCenter,
    GroupRef,
    MemorySession,
    MessageBox,
    PeerRef,
    Session,
    SqliteSession,
    Storage,
    UserRef,
)
from ...tl import Request, abcs
from ..events import Event
from ..events.filters import FilterType
from ..types import (
    AdminRight,
    AlbumBuilder,
    AsyncList,
    Channel,
    ChatRestriction,
    Dialog,
    Draft,
    File,
    Group,
    InFileLike,
    InlineResult,
    KeyboardType,
    LoginToken,
    Message,
    OutFileLike,
    Participant,
    PasswordToken,
    Peer,
    RecentAction,
    User,
)
from .auth import (
    bot_sign_in,
    check_password,
    interactive_login,
    is_authorized,
    request_login_code,
    sign_in,
    sign_out,
)
from .bots import inline_query
from .chats import (
    get_admin_log,
    get_participants,
    get_profile_photos,
    set_chat_default_restrictions,
    set_participant_admin_rights,
    set_participant_restrictions,
)
from .dialogs import delete_dialog, edit_draft, get_dialogs, get_drafts
from .files import (
    download,
    get_file_bytes,
    prepare_album,
    send_audio,
    send_file,
    send_photo,
    send_video,
    upload,
)
from .messages import (
    MessageMap,
    build_message_map,
    delete_messages,
    edit_message,
    forward_messages,
    get_messages,
    get_messages_with_ids,
    pin_message,
    read_message,
    search_all_messages,
    search_messages,
    send_message,
    unpin_message,
)
from .net import (
    Config,
    connect,
    connected,
    default_device_model,
    default_system_version,
    disconnect,
    invoke_request,
    run_until_disconnected,
)
from .updates import (
    add_event_handler,
    get_handler_filter,
    on,
    remove_event_handler,
    set_handler_filter,
)
from .users import get_contacts, get_me, resolve_peers, resolve_phone, resolve_username

Return = TypeVar("Return")


class Client:
    """
    A client capable of connecting to Telegram and sending requests.

    This class can be used as an asynchronous context manager to automatically :meth:`connect` and :meth:`disconnect`:

    .. code-block:: python

        async with Client(session, api_id, api_hash) as client:
            ...  # automatically connect()-ed

        ...  # after exiting the block, disconnect() was automatically called

    :param session:
        A name or path to a ``.session`` file, or a different storage.

    :param api_id:
        The API ID. See :doc:`/basic/signing-in` to learn how to obtain it.

        This is required to initialize the connection.

    :param api_hash:
        The API hash. See :doc:`/basic/signing-in` to learn how to obtain it.

        This is required to sign in, and can be omitted otherwise.

    :param catch_up:
        Whether to "catch up" on updates that occured while the client was not connected.

        If :data:`True`, all updates that occured while the client was offline will trigger your :doc:`event handlers </concepts/updates>`.

    :param check_all_handlers:
        Whether to always check all event handlers or stop early.

        The library will call event handlers in the order they were added.
        By default, the library stops checking handlers as soon as a filter returns :data:`True`.

        By setting ``check_all_handlers=True``, the library will keep calling handlers after the first match.
        Use :class:`telethon.events.Continue` instead if you only want this behaviour sometimes.

    :param flood_sleep_threshold:
        Maximum amount of time, in seconds, to automatically sleep before retrying a request.
        This sleeping occurs when ``FLOOD_WAIT`` (and similar) :class:`~telethon.RpcError`\\ s are raised by Telegram.

    :param logger:
        Logger for the client.
        Any dependency of the client will use :meth:`logging.Logger.getChild`.
        This effectively makes the parameter the root logger.

        The default will get the logger for the package name from the root (usually *telethon*).

    :param update_queue_limit:
        Maximum amount of updates to keep in memory before dropping them.

        A warning will be logged on a cooldown if this limit is reached.

    :param device_model:
        Device model.

    :param system_version:
        System version.

    :param app_version:
        Application version.

    :param system_lang_code:
        `ISO 639-1 <https://www.iso.org/iso-639-language-codes.html>`_ language code of the system's language.

    :param lang_code:
        `ISO 639-1 <https://www.iso.org/iso-639-language-codes.html>`_ language code of the application's language.

    :param datacenter:
        Override the :doc:`data center </concepts/datacenters>` to connect to.
        Useful to connect to one of Telegram's test servers.

    :param connector:
        Asynchronous function called to connect to a remote address.
        By default, this is :func:`asyncio.open_connection`.
        In order to :doc:`use proxies </concepts/datacenters>`, you can set a custom connector.

        See :class:`~telethon._impl.mtsender.sender.Connector` for more details.
    """

    def __init__(
        self,
        session: Optional[str | Path | Storage],
        api_id: int,
        api_hash: Optional[str] = None,
        *,
        catch_up: bool = False,
        check_all_handlers: bool = False,
        flood_sleep_threshold: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
        update_queue_limit: Optional[int] = None,
        device_model: Optional[str] = None,
        system_version: Optional[str] = None,
        app_version: Optional[str] = None,
        system_lang_code: Optional[str] = None,
        lang_code: Optional[str] = None,
        datacenter: Optional[DataCenter] = None,
        connector: Optional[Connector] = None,
        reconnection_policy: Optional[ReconnectionPolicy] = None,
    ) -> None:
        assert __package__
        base_logger = logger or logging.getLogger(__package__[: __package__.index(".")])

        self._sender: Optional[Sender] = None

        if isinstance(session, Storage):
            storage = session
        elif session is None:
            storage = MemorySession()
        else:
            storage = SqliteSession(session)

        self._storage = storage

        self._config = Config(
            api_id=api_id,
            api_hash=api_hash or "",
            device_model=device_model or default_device_model(),
            system_version=system_version or default_system_version(),
            app_version=app_version or default_version,
            system_lang_code=system_lang_code or "en",
            lang_code=lang_code or "en",
            catch_up=catch_up or False,
            datacenter=datacenter,
            flood_sleep_threshold=(
                60 if flood_sleep_threshold is None else flood_sleep_threshold
            ),
            update_queue_limit=update_queue_limit,
            base_logger=base_logger,
            connector=connector or (lambda ip, port: asyncio.open_connection(ip, port)),
            reconnection_policy=reconnection_policy,
        )

        self._session = Session()

        self._message_box = MessageBox(base_logger=base_logger)
        self._chat_hashes = ChatHashCache(None)
        self._last_update_limit_warn: Optional[float] = None
        self._updates: asyncio.Queue[tuple[abcs.Update, dict[int, Peer]]] = (
            asyncio.Queue(maxsize=self._config.update_queue_limit or 0)
        )
        self._dispatcher: Optional[asyncio.Task[None]] = None
        self._handlers: dict[
            Type[Event],
            list[tuple[Callable[[Any], Awaitable[Any]], Optional[FilterType]]],
        ] = {}
        self._check_all_handlers = check_all_handlers

        if self._session.user and self._config.catch_up and self._session.state:
            self._message_box.load(self._session.state)

    # Begin partially @generated

    def add_event_handler(
        self,
        handler: Callable[[Event], Awaitable[Any]],
        /,
        event_cls: Type[Event],
        filter: Optional[FilterType] = None,
    ) -> None:
        """
        Register a callable to be invoked when the provided event type occurs.

        :param handler:
            The callable to invoke when an event occurs.
            This is often just a function object.

        :param event_cls:
            The event type to bind to the handler.
            When Telegram sends an update corresponding to this type,
            *handler* is called with an instance of this event type as the only argument.

        :param filter:
            Filter function to call with the event before calling *handler*.
            If it returns `False`, *handler* will not be called.
            See the :mod:`~telethon.events.filters` module to learn more.

        .. rubric:: Example

        .. code-block:: python

            async def my_print_handler(event):
                print(event.chat.name, event.text)

            # Register a handler to be called on new messages
            client.add_event_handler(my_print_handler, events.NewMessage)

            # Register a handler to be called on new messages if they contain "hello" or "/start"
            from telethon.events import filters

            client.add_event_handler(
                my_print_handler,
                events.NewMessage,
                filters.Any(filters.Text(r'hello'), filters.Command('/start')),
            )

        .. seealso::

            :meth:`on`, used to register handlers with the decorator syntax.
        """
        add_event_handler(self, handler, event_cls, filter)

    async def bot_sign_in(self, token: str) -> User:
        """
        Sign in to a bot account.

        :param token:
            The bot token obtained from `@BotFather <https://t.me/BotFather>`_.
            It's a string composed of digits, a colon, and characters from the base-64 alphabet.

        :return: The bot user corresponding to :term:`yourself`.

        .. rubric:: Example

        .. code-block:: python

            user = await client.bot_sign_in('12345:abc67DEF89ghi')
            print('Signed in to bot account:', user.name)

        .. caution::

            Be sure to check :meth:`is_authorized` before calling this function.
            Signing in often when you don't need to will lead to :doc:`/concepts/errors`.

        .. seealso::

            :meth:`request_login_code`, used to sign in as a user instead.
        """
        return await bot_sign_in(self, token)

    async def check_password(self, token: PasswordToken, password: str | bytes) -> User:
        """
        Check the two-factor-authentication (2FA) password.
        If it is correct, completes the login.

        :param token:
            The return value from :meth:`sign_in`.

        :param password:
            The 2FA password.

        :return: The user corresponding to :term:`yourself`.

        .. rubric:: Example

        .. code-block:: python

            from telethon.types import PasswordToken

            login_token = await client.request_login_code('+1 23 456')
            password_token = await client.sign_in(login_token, input('code: '))
            assert isinstance(password_token, PasswordToken)

            user = await client.check_password(password_token, '1-L0V3+T3l3th0n')
            print('Signed in to 2FA-protected account:', user.name)

        .. seealso::

            :meth:`request_login_code` and :meth:`sign_in`
        """
        return await check_password(self, token, password)

    async def connect(self) -> None:
        """
        Connect to the Telegram servers.

        .. rubric:: Example

        .. code-block:: python

            await client.connect()
            # success!
        """
        await connect(self)

    async def delete_dialog(self, dialog: Peer | PeerRef, /) -> None:
        """
        Delete a dialog.

        This lets you leave a group, unsubscribe from a channel, or delete a one-to-one private conversation.

        Note that the group or channel will not be deleted (other users will remain in it).

        Note that bot accounts do not have dialogs, so this method will fail when used in a bot account.

        :param dialog:
            The :term:`peer` representing the dialog to delete.

        .. rubric:: Example

        .. code-block:: python

            async for dialog in client.iter_dialogs():
                if 'dog pictures' in dialog.chat.name:
                    # You've realized you're more of a cat person
                    await client.delete_dialog(dialog.chat)
        """
        await delete_dialog(self, dialog)

    async def delete_messages(
        self, chat: Peer | PeerRef, /, message_ids: list[int], *, revoke: bool = True
    ) -> int:
        """
        Delete messages.

        :param chat:
            The :term:`peer` where the messages are.

            .. warning::

                When deleting messages from private conversations or small groups,
                this parameter is currently ignored.
                This means the *message_ids* may delete messages in different chats.

        :param message_ids:
            The list of message identifiers to delete.

        :param revoke:
            When set to :data:`True`, the message will be deleted for everyone that is part of *chat*.
            Otherwise, the message will only be deleted for :term:`yourself`.

        :return: The amount of messages that were deleted.

        .. rubric:: Example

        .. code-block:: python

            # Delete two messages from chat for yourself
            delete_count = await client.delete_messages(
                chat,
                [187481, 187482],
                revoke=False,
            )
            print('Deleted', delete_count, 'message(s)')

        .. seealso::

            :meth:`telethon.types.Message.delete`
        """
        return await delete_messages(self, chat, message_ids, revoke=revoke)

    async def disconnect(self) -> None:
        """
        Disconnect from the Telegram servers.

        This call will only fail if saving the :term:`session` fails.

        .. rubric:: Example

        .. code-block:: python

            await client.disconnect()
            # success!
        """
        await disconnect(self)

    async def download(self, media: File, /, file: str | Path | OutFileLike) -> None:
        """
        Download a file.

        :param media:
            The media file to download.
            This will often come from :attr:`telethon.types.Message.file`.

        :param file:
            The output file path or :term:`file-like object`.
            Note that the extension is not automatically added to the path.
            You can get the file extension with :attr:`telethon.types.File.ext`.

            .. caution::

                If the file already exists, it will be overwritten.

        .. rubric:: Example

        .. code-block:: python

            if photo := message.photo:
                await client.download(photo, f'picture{photo.ext}')

            if video := message.video:
                with open(f'video{video.ext}', 'wb') as file:
                    await client.download(video, file)

        .. seealso::

            :meth:`get_file_bytes`, for more control over the download.
        """
        await download(self, media, file)

    async def edit_draft(
        self,
        peer: Peer | PeerRef,
        /,
        text: Optional[str] = None,
        *,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
        reply_to: Optional[int] = None,
    ) -> Draft:
        """
        Set a draft message in a chat.

        This can also be used to clear the draft by setting the text to an empty string ``""``.

        :param peer:
            The :term:`peer` where the draft will be saved to.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :ref:`formatting`.

        :param reply_to:
            The message identifier of the message to reply to.

        :return: The created draft.

        .. rubric:: Example

        .. code-block:: python

            # Set a draft with no formatting and print the date Telegram registered
            draft = await client.edit_draft(chat, 'New text')
            print('Set current draft on', draft.date)

            # Set a draft using HTML formatting, with a reply, and enabling the link preview
            await client.edit_draft(
                chat,
                html='Draft with <em>reply</em> an URL https://example.com',
                reply_to=message_id,
                link_preview=True
            )

        .. seealso::

            :meth:`telethon.types.Draft.edit`
        """
        return await edit_draft(
            self,
            peer,
            text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
            reply_to=reply_to,
        )

    async def edit_message(
        self,
        chat: Peer | PeerRef,
        /,
        message_id: int,
        *,
        text: Optional[str] = None,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Edit a message.

        :param chat:
            The :term:`peer` where the message to edit is.

        :param message_id:
            The identifier of the message to edit.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :ref:`formatting`.
        :param keyboard:
            The keyboard to use for the message.

            Only bot accounts can send keyboard.

        :return: The edited message.

        .. rubric:: Example

        .. code-block:: python

            # Edit message to have text without formatting
            await client.edit_message(chat, msg_id, text='New text')

            # Remove the link preview without changing the text
            await client.edit_message(chat, msg_id, link_preview=False)

        .. seealso::

            :meth:`telethon.types.Message.edit`
        """
        return await edit_message(
            self,
            chat,
            message_id,
            text=text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
            keyboard=keyboard,
        )

    async def forward_messages(
        self, target: Peer | PeerRef, message_ids: list[int], source: Peer | PeerRef
    ) -> list[Message]:
        """
        Forward messages from one :term:`peer` to another.

        :param target:
            The :term:`peer` where the messages will be forwarded to.

        :param message_ids:
            The list of message identifiers to forward.

        :param source:
            The source :term:`peer` where the messages to forward exist.

        :return: The forwarded messages.

        .. rubric:: Example

        .. code-block:: python

            # Forward two messages from chat to the destination
            messages = await client.forward_messages(
                destination,
                [187481, 187482],
                chat,
            )
            print('Forwarded', len(messages), 'message(s)')

        .. seealso::

            :meth:`telethon.types.Message.forward`
        """
        return await forward_messages(self, target, message_ids, source)

    def get_admin_log(
        self, chat: Group | Channel | GroupRef | ChannelRef, /
    ) -> AsyncList[RecentAction]:
        """
        Get the recent actions from the administrator's log.

        This method requires you to be an administrator in the :term:`peer`.

        The returned actions are also known as "admin log events".

        :param chat:
            The :term:`peer` to fetch recent actions from.

        :return: The recent actions.

        .. rubric:: Example

        .. code-block:: python

            async for admin_log_event in client.get_admin_log(chat):
                if message := admin_log_event.deleted_message:
                    print('Deleted:', message.text)
        """
        return get_admin_log(self, chat)

    def get_contacts(self) -> AsyncList[User]:
        """
        Get the users in your contact list.

        :return: Your contacts.

        .. rubric:: Example

        .. code-block:: python

            async for user in client.get_contacts():
                print(user.name, user.id)
        """
        return get_contacts(self)

    def get_dialogs(self) -> AsyncList[Dialog]:
        """
        Get the dialogs you're part of.

        This list of includes the groups you've joined, channels you've subscribed to, and open one-to-one private conversations.

        Note that bot accounts do not have dialogs, so this method will fail.

        :return: Your dialogs.

        .. rubric:: Example

        .. code-block:: python

            async for dialog in client.get_dialogs():
                print(
                    dialog.chat.name,
                    dialog.last_message.text if dialog.last_message else ''
                )
        """
        return get_dialogs(self)

    def get_drafts(self) -> AsyncList[Draft]:
        """
        Get all message drafts saved in any dialog.

        :return: The existing message drafts.

        .. rubric:: Example

        .. code-block:: python

            # Clear all drafts
            async for draft in client.get_drafts():
                await draft.delete()
        """
        return get_drafts(self)

    def get_file_bytes(self, media: File, /) -> AsyncList[bytes]:
        """
        Get the contents of an uploaded media file as chunks of :class:`bytes`.

        This lets you iterate over the chunks of a file and print progress while the download occurs.

        If you just want to download a file to disk without printing progress, use :meth:`download` instead.

        :param media:
            The media file to download.
            This will often come from :attr:`telethon.types.Message.file`.

        .. rubric:: Example

        .. code-block:: python

            if file := message.file:
                with open(f'media{file.ext}', 'wb') as fd:
                    downloaded = 0
                    async for chunk in client.get_file_bytes(file):
                        downloaded += len(chunk)
                        fd.write(chunk)
                        print(f'Downloaded {downloaded // 1024}/{file.size // 1024} KiB')
        """
        return get_file_bytes(self, media)

    def get_handler_filter(
        self, handler: Callable[[Event], Awaitable[Any]], /
    ) -> Optional[FilterType]:
        """
        Get the filter associated to the given event handler.

        :param handler:
            The callable that was previously added as an event handler.

        :return:
            The filter, if *handler* was actually registered and had a filter.

        .. rubric:: Example

        .. code-block:: python

            from telethon.events import filters

            # Get the current filter...
            filt = client.get_handler_filter(my_handler)

            # ...and "append" a new filter that also must match.
            client.set_handler_filter(my_handler, filters.All(filt, filt.Text(r'test')))
        """
        return get_handler_filter(self, handler)

    async def get_me(self) -> Optional[User]:
        """
        Get information about :term:`yourself`.

        :return:
            The user associated with the logged-in account, or :data:`None` if the client is not authorized.

        .. rubric:: Example

        .. code-block:: python

            me = await client.get_me()
            assert me is not None, "not logged in!"

            if me.bot:
                print('I am a bot')

            print('My name is', me.name)

            if me.phone:
                print('My phone number is', me.phone)
        """
        return await get_me(self)

    def get_messages(
        self,
        chat: Peer | PeerRef,
        /,
        limit: Optional[int] = None,
        *,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        """
        Get the message history from a :term:`peer`, from the newest message to the oldest.

        The returned iterator can be :func:`reversed` to fetch from the first to the last instead.

        :param chat:
            The :term:`peer` where the messages should be fetched from.

        :param limit:
            How many messages to fetch at most.

            .. caution::

                By default, there is no limit, so the method will fetch all messages.
                This means :keyword:`await` may appear to hang if there are thousands of messages in the chat.
                You can either set a smaller limit or use the ``async for`` syntax instead.

        :param offset_id:
            Start getting messages with an identifier lower than this one.
            This means only messages older than the message with ``id = offset_id`` will be fetched.

        :param offset_date:
            Start getting messages with a date lower than this one.
            This means only messages sent before *offset_date* will be fetched.

        :return: The message history.

        .. rubric:: Example

        .. code-block:: python

            # Get the last message in a chat
            last_message = (await client.get_messages(chat, 1))[0]
            print(message.sender.name, last_message.text)

            # Print all messages before 2023 as HTML
            from datetime import datetime

            async for message in client.get_messages(chat, offset_date=datetime(2023, 1, 1)):
                print(message.sender.name, ':', message.html_text)

            # Print the first 10 messages in a chat as markdown
            async for message in reversed(client.get_messages(chat)):
                print(message.sender.name, ':', message.markdown_text)
        """
        return get_messages(
            self, chat, limit, offset_id=offset_id, offset_date=offset_date
        )

    def get_messages_with_ids(
        self, chat: Peer | PeerRef, /, message_ids: list[int]
    ) -> AsyncList[Message]:
        """
        Get the full message objects from the corresponding message identifiers.

        :param chat:
            The :term:`peer` where the message to fetch is.

        :param message_ids:
            The message identifiers of the messages to fetch.

        :return:
            The matching messages.
            The order of the returned messages is *not* guaranteed to match the input.
            The method may return less messages than requested when some are missing.

        .. rubric:: Example

        .. code-block:: python

            # Get the first message (after "Channel created") of the chat
            first_message = (await client.get_messages_with_ids(chat, [2]))[0]
        """
        return get_messages_with_ids(self, chat, message_ids)

    def get_participants(
        self, chat: Group | Channel | GroupRef | ChannelRef, /
    ) -> AsyncList[Participant]:
        """
        Get the participants in a group or channel, along with their permissions.

        .. note::

            Telegram is rather strict when it comes to fetching members.
            It is very likely that you will not be able to fetch all the members.
            There is no way to bypass this.

        :param chat:
            The :term:`peer` to fetch participants from.

        :return: The participants.

        .. rubric:: Example

        .. code-block:: python

            async for participant in client.get_participants(chat):
                print(participant.user.name)
        """
        return get_participants(self, chat)

    def get_profile_photos(self, peer: Peer | PeerRef, /) -> AsyncList[File]:
        """
        Get the profile pictures set in a chat, or user avatars.

        :param peer:
            The :term:`peer` to fetch the profile photo files from.

        :return: The photo files.

        .. rubric:: Example

        .. code-block:: python

            i = 0
            async for photo in client.get_profile_photos(chat):
                await client.download(photo, f'{i}.jpg')
                i += 1
        """
        return get_profile_photos(self, peer)

    async def inline_query(
        self,
        bot: User | UserRef,
        /,
        query: str = "",
        *,
        peer: Optional[Peer | PeerRef] = None,
    ) -> AsyncIterator[InlineResult]:
        """
        Perform a *@bot inline query*.

        It's known as inline because clients with a GUI display the results *inline*,
        after typing on the message input textbox, without sending any message.

        :param bot:
            The bot to sent the query string to.

        :param query:
            The query string to send to the bot.

        :param peer:
            Where the query is being made and will be sent.
            Some bots display different results based on the type of chat.

        :return: The query results returned by the bot.

        .. rubric:: Example

        .. code-block:: python

            i = 0

            # This is equivalent to typing "@bot songs" in an official client
            async for result in client.inline_query(bot, 'songs'):
                if 'keyword' in result.title:
                    await result.send(chat)
                    break

                i += 1
                if i == 10:
                    break  # did not find 'keyword' in the first few results
        """
        return await inline_query(self, bot, query, peer=peer)

    async def interactive_login(
        self, phone_or_token: Optional[str] = None, *, password: Optional[str] = None
    ) -> User:
        """
        Begin an interactive login if needed.
        If the account was already logged-in, this method simply returns :term:`yourself`.

        :param phone_or_token:
            Bypass the phone number or bot token prompt, and use this value instead.

        :param password:
            Bypass the 2FA password prompt, and use this value instead.

        :return: The user corresponding to :term:`yourself`.

        .. rubric:: Example

        .. code-block:: python

            # Interactive login from the terminal
            me = await client.interactive_login()
            print('Logged in as:', me.name)

            # Automatic login to a bot account
            await client.interactive_login('54321:hJrIQtVBab0M2Yqg4HL1K-EubfY_v2fEVR')

        .. seealso::

            In-depth explanation for :doc:`/basic/signing-in`.
        """
        return await interactive_login(self, phone_or_token, password=password)

    async def is_authorized(self) -> bool:
        """
        Check whether the client instance is authorized (i.e. logged-in).

        :return: :data:`True` if the client instance has signed-in.

        .. rubric:: Example

        .. code-block:: python

            if not await client.is_authorized():
                ...  # need to sign in

        .. seealso::

            :meth:`get_me` can be used to fetch up-to-date information about :term:`yourself`
            and check if you're logged-in at the same time.
        """
        return await is_authorized(self)

    def on(
        self, event_cls: Type[Event], /, filter: Optional[FilterType] = None
    ) -> Callable[
        [Callable[[Event], Awaitable[Any]]], Callable[[Event], Awaitable[Any]]
    ]:
        """
        Register the decorated function to be invoked when the provided event type occurs.

        :param event_cls:
            The event type to bind to the handler.
            When Telegram sends an update corresponding to this type,
            the decorated function is called with an instance of this event type as the only argument.

        :param filter:
            Filter function to call with the event before calling *handler*.
            If it returns `False`, *handler* will not be called.
            See the :mod:`~telethon.events.filters` module to learn more.

        :return: The decorator.

        .. rubric:: Example

        .. code-block:: python

            # Register a handler to be called on new messages
            @client.on(events.NewMessage)
            async def my_print_handler(event):
                print(event.chat.name, event.text)

            # Register a handler to be called on new messages if they contain "hello" or "/start"
            from telethon.events.filters import Any, Text, Command

            @client.on(events.NewMessage, Any(Text(r'hello'), Command('/start')))
            async def my_other_print_handler(event):
                print(event.chat.name, event.text)

        .. seealso::

            :meth:`add_event_handler`, used to register existing functions as event handlers.
        """
        return on(self, event_cls, filter)

    async def pin_message(self, chat: Peer | PeerRef, /, message_id: int) -> Message:
        """
        Pin a message to be at the top.

        :param chat:
            The :term:`peer` where the message to pin is.

        :param message_id:
            The identifier of the message to pin.

        :return: The service message announcing the pin.

        .. rubric:: Example

        .. code-block:: python

            # Pin a message, then delete the service message
            message = await client.pin_message(chat, 187481)
            await message.delete()
        """
        return await pin_message(self, chat, message_id)

    def prepare_album(self) -> AlbumBuilder:
        """
        Prepare an album upload to send.

        Albums are a way to send multiple photos or videos as separate messages with the same grouped identifier.

        :return: A new album builder instance, with no media added to it yet.

        .. rubric:: Example

        .. code-block:: python

            # Prepare a new album
            album = await client.prepare_album()

            # Add a bunch of photos
            for photo in ('a.jpg', 'b.png'):
                await album.add_photo(photo)
            # A video in-between
            await album.add_video('c.mp4')
            # And another photo
            await album.add_photo('d.jpeg')

            # Album is ready to be sent to as many chats as needed
            await album.send(chat)
        """
        return prepare_album(self)

    async def read_message(
        self, chat: Peer | PeerRef, /, message_id: int | Literal["all"]
    ) -> None:
        """
        Mark messages as read.

        This will send a read acknowledgment to all messages with identifiers below and up-to the given message identifier.

        This is often represented as a blue double-check (✓✓).

        A single check (✓) in Telegram often indicates the message was sent and perhaps received, but not read.

        A clock (🕒) in Telegram often indicates the message was not yet sent at all.
        This most commonly occurs when sending messages without a network connection.

        :param chat:
            The chat where the messages to be marked as read are.

        :param message_id:
            The identifier of the message to mark as read.
            All messages older (sent before) this one will also be marked as read.

            The literal ``'all'`` may be used to mark all messages in a chat as read.

        .. rubric:: Example

        .. code-block:: python

            # Mark all messages as read
            await client.read_message(chat, 'all')
        """
        await read_message(self, chat, message_id)

    def remove_event_handler(
        self, handler: Callable[[Event], Awaitable[Any]], /
    ) -> None:
        """
        Remove the handler as a function to be called when events occur.
        This is simply the opposite of :meth:`add_event_handler`.
        Does nothing if the handler was not actually registered.

        :param handler:
            The callable to stop invoking when events occur.

        .. rubric:: Example

        .. code-block:: python

            # Register a handler that removes itself when it receives 'stop'
            @client.on(events.NewMessage)
            async def my_handler(event):
                if 'stop' in event.text:
                    client.remove_event_handler(my_handler)
                else:
                    print('still going!')
        """
        remove_event_handler(self, handler)

    async def request_login_code(self, phone: str) -> LoginToken:
        """
        Request Telegram to send a login code to the provided phone number.

        :param phone:
            The phone number string, in international format.
            The plus-sign ``+`` can be kept in the string.

        :return: Information about the sent code.

        .. rubric:: Example

        .. code-block:: python

            login_token = await client.request_login_code('+1 23 456...')
            print(login_token.timeout, 'seconds before code expires')

        .. caution::

            Be sure to check :meth:`is_authorized` before calling this function.
            Signing in often when you don't need to will lead to :doc:`/concepts/errors`.

        .. seealso::

            :meth:`sign_in`, to complete the login procedure.
        """
        return await request_login_code(self, phone)

    async def resolve_peers(self, peers: Sequence[Peer | PeerRef], /) -> list[Peer]:
        """
        Resolve one or more peer references into peer objects.

        This methods also accepts peer objects as input, which will be refetched but not mutated in-place.

        :param peers:
            The peers to fetch.

        :return: The fetched peers, in the same order as the input.

        .. rubric:: Example

        .. code-block:: python

            [user, group, channel] = await client.resolve_peers([
                user_ref, group_ref, channel_ref
            ])
        """
        return await resolve_peers(self, peers)

    async def resolve_phone(self, phone: str, /) -> Peer:
        """
        Resolve a phone number into a :term:`peer`.

        This method is rather expensive to call.
        It is recommended to use it once and then store the :attr:`types.Peer.ref`.

        :param phone:
            The phone number "+1 23 456" to resolve.
            The phone number must contain the `International Calling Code <https://en.wikipedia.org/wiki/List_of_mobile_telephone_prefixes_by_country>`_.
            You do not need to use include the ``'+'`` prefix, but the parameter must be a :class:`str`, not :class:`int`.

        :return: The matching chat.

        .. rubric:: Example

        .. code-block:: python

            print(await client.resolve_phone('+1 23 456'))
        """
        return await resolve_phone(self, phone)

    async def resolve_username(self, username: str, /) -> Peer:
        """
        Resolve a username into a :term:`peer`.

        This method is rather expensive to call.
        It is recommended to use it once and then store the :attr:`types.Peer.ref`.

        :param username:
            The public "@username" to resolve.
            You do not need to use include the ``'@'`` prefix.
            Links cannot be used.

        :return: The matching chat.

        .. rubric:: Example

        .. code-block:: python

            print(await client.resolve_username('@cat'))
        """
        return await resolve_username(self, username)

    async def run_until_disconnected(self) -> None:
        """
        Keep running the library until a disconnection occurs.

        Connection errors will be raised from this method if they occur.
        """
        await run_until_disconnected(self)

    def search_all_messages(
        self,
        limit: Optional[int] = None,
        *,
        query: Optional[str] = None,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        """
        Perform a global message search.
        This is used to search messages in no particular chat (i.e. everywhere possible).

        :param limit:
            How many messages to fetch at most.

            .. note::

                Like :meth:`get_messages`, there is no limit by default, so :keyword:`await` may appear to hang.

        :param query:
            Text query to use for fuzzy matching messages.
            The rules for how "fuzzy" works are an implementation detail of the server.

        :param offset_id:
            Start getting messages with an identifier lower than this one.
            This means only messages older than the message with ``id = offset_id`` will be fetched.

        :param offset_date:
            Start getting messages with a date lower than this one.
            This means only messages sent before *offset_date* will be fetched.

        :return: The found messages.

        .. rubric:: Example

        .. code-block:: python

            async for message in client.search_all_messages(query='hello'):
                print(message.text)
        """
        return search_all_messages(
            self, limit, query=query, offset_id=offset_id, offset_date=offset_date
        )

    def search_messages(
        self,
        chat: Peer | PeerRef,
        /,
        limit: Optional[int] = None,
        *,
        query: Optional[str] = None,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        """
        Search messages in a chat.

        :param chat:
            The :term:`peer` where messages will be searched.

        :param limit:
            How many messages to fetch at most.

            .. note::

                Like :meth:`get_messages`, there is no limit by default, so :keyword:`await` may appear to hang.

        :param query:
            Text query to use for fuzzy matching messages.
            The rules for how "fuzzy" works are an implementation detail of the server.

        :param offset_id:
            Start getting messages with an identifier lower than this one.
            This means only messages older than the message with ``id = offset_id`` will be fetched.

        :param offset_date:
            Start getting messages with a date lower than this one.
            This means only messages sent before *offset_date* will be fetched.

        :return: The found messages.

        .. rubric:: Example

        .. code-block:: python

            async for message in client.search_messages(chat, query='hello'):
                print(message.text)
        """
        return search_messages(
            self, chat, limit, query=query, offset_id=offset_id, offset_date=offset_date
        )

    async def send_audio(
        self,
        chat: Peer | PeerRef,
        /,
        file: str | Path | InFileLike | File,
        *,
        size: Optional[int] = None,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        duration: Optional[float] = None,
        voice: bool = False,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
        reply_to: Optional[int] = None,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Send an audio file.

        Unlike :meth:`send_file`, this method will attempt to guess the values for
        duration, title and performer if they are not provided.

        :param chat:
            The :term:`peer` where the audio media will be sent to.

        :param file: See :meth:`send_file`.
        :param size: See :meth:`send_file`.
        :param name: See :meth:`send_file`.
        :param mime_type: See :meth:`send_file`.
        :param duration: See :meth:`send_file`.
        :param voice: See :meth:`send_file`.
        :param title: See :meth:`send_file`.
        :param performer: See :meth:`send_file`.
        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.

        .. rubric:: Example

        .. code-block:: python

            await client.send_audio(chat, 'file.ogg', voice=True)
        """
        return await send_audio(
            self,
            chat,
            file,
            size=size,
            name=name,
            mime_type=mime_type,
            duration=duration,
            voice=voice,
            title=title,
            performer=performer,
            caption=caption,
            caption_markdown=caption_markdown,
            caption_html=caption_html,
            reply_to=reply_to,
            keyboard=keyboard,
        )

    async def send_file(
        self,
        chat: Peer | PeerRef,
        /,
        file: str | Path | InFileLike | File,
        *,
        size: Optional[int] = None,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        compress: bool = False,
        animated: bool = False,
        duration: Optional[float] = None,
        voice: bool = False,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        emoji: Optional[str] = None,
        emoji_sticker: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        round: bool = False,
        supports_streaming: bool = False,
        muted: bool = False,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
        reply_to: Optional[int] = None,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Send any type of file with any amount of attributes.

        This method will *not* attempt to guess any of the file metadata such as width, duration, title, etc.
        If you want to let the library attempt to guess the file metadata, use the type-specific methods to send media:
        `send_photo`, `send_audio` or `send_file`.

        Unlike :meth:`send_photo`, image files will be sent as documents by default.

        :param chat:
            The :term:`peer` where the message will be sent to.

        :param path:
            A local file path or :class:`~telethon.types.File` to send.

        :param file:
            The file to send.

            This can be a path, relative or absolute, to a local file, as either a :class:`str` or :class:`pathlib.Path`.

            It can also be a file opened for reading in binary mode, with its ``read`` method optionally being ``async``.
            Note that the file descriptor will *not* be seeked back to the start before sending it.

            If you wrote to an in-memory file, you probably want to ``file.seek(0)`` first.
            If you want to send :class:`bytes`, wrap them in :class:`io.BytesIO` first.

            You can also pass any :class:`~telethon.types.File` that was previously sent in Telegram to send a copy.
            This will not download and re-upload the file, but will instead reuse the original without forwarding it.

            Last, a URL can also be specified.
            For the library to detect it as a URL, the string *must* start with either ``http://` or ``https://``.
            Telethon will *not* download and upload the file, but will instead pass the URL to Telegram.
            If Telegram is unable to access the media, is too large, or is invalid, the method will fail.

            When using URLs, it is recommended to explicitly pass either a name or define the mime-type.
            To make sure the URL is interpreted as an image, use `send_photo`.

        :param size:
            The size of the local file to send.

            This parameter **must** be specified when sending a previously-opened or in-memory files.
            The library will not ``seek`` the file to attempt to determine the size.

            This can be less than the real file size, in which case only ``size`` bytes will be sent.
            This can be useful if you have a single buffer with multiple files.

        :param name:
            Override for the default file name.

            When given a string or path, its :attr:`~pathlib.PurePath.name` will be used by default only if this parameter is omitted.

            When given a :term:`file-like object`, if it has a ``.name`` :class:`str` property, it will be used.
            This is the case for files opened via :func:`open`.

            This parameter **must** be specified when sending any other previously-opened or in-memory files.

        :param mime_type:
            Override for the default mime-type.

            By default, the library will use :func:`mimetypes.guess_type` on the name.

            If no mime-type is registered for the name's extension, ``application/octet-stream`` will be used.

        :param compress:
            Whether the image file is allowed to be compressed by Telegram.

            If not, image files will be sent as document.

        :param animated:
            Whether the sticker is animated (not a static image).

        :param duration:
            Duration, in seconds, of the audio or video.

            This field should be specified when sending audios or videos from local files.

            The floating-point value will be rounded to an integer.

        :param voice:
            Whether the audio is a live recording, often recorded right before sending it.

        :param title:
            Title of the song in the audio file.

        :param performer:
            Artist or main performer of the song in the audio file.

        :param emoji:
            Alternative text for the sticker.

        :param width:
            Width, in pixels, of the image or video.

            This field should be specified when sending images or videos from local files.

        :param height:
            Height, in pixels, of the image or video.

            This field should be specified when sending images or videos from local files.

        :param round:
            Whether the video should be displayed as a round video.

        :param supports_streaming:
            Whether clients are allowed to stream the video having to wait for a full download.

            Note that the file format of the video must have streaming support.

        :param muted:
            Whether the sound of the video is or should be missing.

            This is often used for short animations or "GIFs".

        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.

        .. rubric:: Example

        .. code-block:: python

            await client.send_file(chat, 'picture.jpg')

            # Sending in-memory bytes
            import io
            data = b'my in-memory document'
            cawait client.send_file(chat, io.BytesIO(data), size=len(data), name='doc.txt')
        """
        return await send_file(
            self,
            chat,
            file,
            size=size,
            name=name,
            mime_type=mime_type,
            compress=compress,
            animated=animated,
            duration=duration,
            voice=voice,
            title=title,
            performer=performer,
            emoji=emoji,
            emoji_sticker=emoji_sticker,
            width=width,
            height=height,
            round=round,
            supports_streaming=supports_streaming,
            muted=muted,
            caption=caption,
            caption_markdown=caption_markdown,
            caption_html=caption_html,
            reply_to=reply_to,
            keyboard=keyboard,
        )

    async def send_message(
        self,
        chat: Peer | PeerRef,
        /,
        text: Optional[str | Message] = None,
        *,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: bool = False,
        reply_to: Optional[int] = None,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Send a message.

        :param chat:
            The :term:`peer` where the message will be sent to.

        :param text: See :ref:`formatting`.
        :param markdown: See :ref:`formatting`.
        :param html: See :ref:`formatting`.
        :param link_preview: See :ref:`formatting`.

        :param reply_to:
            The message identifier of the message to reply to.

        :param keyboard:
            The keyboard to use for the message.

            Only bot accounts can send keyboard.

        .. rubric:: Example

        .. code-block:: python

            await client.send_message(chat, markdown='**Hello!**')
        """
        return await send_message(
            self,
            chat,
            text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
            reply_to=reply_to,
            keyboard=keyboard,
        )

    async def send_photo(
        self,
        chat: Peer | PeerRef,
        /,
        file: str | Path | InFileLike | File,
        *,
        size: Optional[int] = None,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        compress: bool = True,
        width: Optional[int] = None,
        height: Optional[int] = None,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
        reply_to: Optional[int] = None,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Send a photo file.

        By default, the server will be allowed to `compress` the image.
        Only compressed images can be displayed as photos in applications.
        If *compress* is set to :data:`False`, the image will be sent as a file document.

        Unlike :meth:`send_file`, this method will attempt to guess the values for
        width and height if they are not provided.

        :param chat:
            The :term:`peer` where the photo media will be sent to.

        :param file: See :meth:`send_file`.
        :param size: See :meth:`send_file`.
        :param name: See :meth:`send_file`.
        :param mime_type: See :meth:`send_file`.
        :param compress: See :meth:`send_file`.
        :param width: See :meth:`send_file`.
        :param height: See :meth:`send_file`.
        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.

        .. rubric:: Example

        .. code-block:: python

            await client.send_photo(chat, 'photo.jpg', caption='Check this out!')
        """
        return await send_photo(
            self,
            chat,
            file,
            size=size,
            name=name,
            mime_type=mime_type,
            compress=compress,
            width=width,
            height=height,
            caption=caption,
            caption_markdown=caption_markdown,
            caption_html=caption_html,
            reply_to=reply_to,
            keyboard=keyboard,
        )

    async def send_video(
        self,
        chat: Peer | PeerRef,
        /,
        file: str | Path | InFileLike | File,
        *,
        size: Optional[int] = None,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        duration: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        round: bool = False,
        supports_streaming: bool = False,
        muted: bool = False,
        caption: Optional[str] = None,
        caption_markdown: Optional[str] = None,
        caption_html: Optional[str] = None,
        reply_to: Optional[int] = None,
        keyboard: Optional[KeyboardType] = None,
    ) -> Message:
        """
        Send a video file.

        Unlike :meth:`send_file`, this method will attempt to guess the values for
        duration, width and height if they are not provided.

        :param chat:
            The :term:`peer` where the message will be sent to.

        :param file: See :meth:`send_file`.
        :param size: See :meth:`send_file`.
        :param name: See :meth:`send_file`.
        :param mime_type: See :meth:`send_file`.
        :param duration: See :meth:`send_file`.
        :param width: See :meth:`send_file`.
        :param height: See :meth:`send_file`.
        :param round: See :meth:`send_file`.
        :param supports_streaming: See :meth:`send_file`.
        :param caption: See :ref:`formatting`.
        :param caption_markdown: See :ref:`formatting`.
        :param caption_html: See :ref:`formatting`.

        .. rubric:: Example

        .. code-block:: python

            await client.send_video(chat, 'video.mp4', caption_markdown='*I cannot believe this just happened*')
        """
        return await send_video(
            self,
            chat,
            file,
            size=size,
            name=name,
            mime_type=mime_type,
            duration=duration,
            width=width,
            height=height,
            round=round,
            supports_streaming=supports_streaming,
            muted=muted,
            caption=caption,
            caption_markdown=caption_markdown,
            caption_html=caption_html,
            reply_to=reply_to,
            keyboard=keyboard,
        )

    async def set_chat_default_restrictions(
        self,
        chat: Peer | PeerRef,
        /,
        restrictions: Sequence[ChatRestriction],
        *,
        until: Optional[datetime.datetime] = None,
    ) -> None:
        """
        Set the default restrictions to apply to all participant in a chat.

        :param chat:
            The :term:`peer` where the restrictions will be applied.

        :param restrictions:
            The sequence of restrictions to apply.

        :param until:
            Date until which the restrictions should be applied.
            By default, restrictions apply for as long as possible.

        .. rubric:: Example

        .. code-block:: python

            from datetime import datetime, timedelta
            from telethon.types import ChatRestriction

            # Don't allow anyone except administrators to send stickers for a day
            await client.set_chat_default_restrictions(
                chat, user, [ChatRestriction.SEND_STICKERS],
                until=datetime.now() + timedelta(days=1))

            # Remove all default restrictions from the chat
            await client.set_chat_default_restrictions(chat, user, [])

        .. seealso::

            :meth:`telethon.types.Group.set_default_restrictions`
        """
        await set_chat_default_restrictions(self, chat, restrictions, until=until)

    def set_handler_filter(
        self,
        handler: Callable[[Event], Awaitable[Any]],
        /,
        filter: Optional[FilterType] = None,
    ) -> None:
        """
        Set the filter to use for the given event handler.

        :param handler:
            The callable that was previously added as an event handler.

        :param filter:
            The filter to use for *handler*, or :data:`None` to remove the old filter.

        .. rubric:: Example

        .. code-block:: python

            from telethon.events import filters

            # Change the filter to handle '/stop'
            client.set_handler_filter(my_handler, filters.Command('/stop'))

            # Remove the filter
            client.set_handler_filter(my_handler, None)
        """
        set_handler_filter(self, handler, filter)

    async def set_participant_admin_rights(
        self,
        chat: Group | Channel | GroupRef | ChannelRef,
        /,
        participant: User | UserRef,
        rights: Sequence[AdminRight],
    ) -> None:
        """
        Set the administrator rights granted to the participant in the chat.

        If an empty sequence of rights is given, the user will be demoted and stop being an administrator.

        In small group chats, there are no separate administrator rights.
        In this case, granting any right will make the user an administrator with all rights.

        :param chat:
            The :term:`peer` where the rights will be granted.

        :param participant:
            The participant to promote to administrator, usually a :class:`types.User`.

        :param rights:
            The sequence of rights to grant.
            Can be empty to revoke the administrator status from the participant.

        .. rubric:: Example

        .. code-block:: python

            from telethon.types import AdminRight

            # Make user an administrator allowed to pin messages
            await client.set_participant_admin_rights(
                chat, user, [AdminRight.PIN_MESSAGES])

            # Demote an administrator
            await client.set_participant_admin_rights(chat, user, [])

        .. seealso::

            :meth:`telethon.types.Participant.set_admin_rights`
        """
        await set_participant_admin_rights(self, chat, participant, rights)

    async def set_participant_restrictions(
        self,
        chat: Group | Channel | GroupRef | ChannelRef,
        /,
        participant: Peer | PeerRef,
        restrictions: Sequence[ChatRestriction],
        *,
        until: Optional[datetime.datetime] = None,
    ) -> None:
        """
        Set the restrictions to apply to a participant in the chat.

        Restricting the participant to :attr:`~types.ChatRestriction.VIEW_MESSAGES` will kick them out of the chat.

        In small group chats, there are no separate restrictions.
        In this case, any restriction will kick the participant.
        The participant's history will be revoked if the restriction to :attr:`~types.ChatRestriction.VIEW_MESSAGES` is applied.

        :param chat:
            The :term:`peer` where the restrictions will be applied.

        :param participant:
            The participant to restrict or ban, usually a :class:`types.User`.

        :param restrictions:
            The sequence of restrictions to apply.
            Can be empty to remove all restrictions from the participant and unban them.

        :param until:
            Date until which the restrictions should be applied.
            By default, restrictions apply for as long as possible.

        .. rubric:: Example

        .. code-block:: python

            from datetime import datetime, timedelta
            from telethon.types import ChatRestriction

            # Kick the user out of the chat
            await client.set_participant_restrictions(
                chat, user, [ChatRestriction.VIEW_MESSAGES])

            # Don't allow the user to send media for 5 minutes
            await client.set_participant_restrictions(
                chat, user, [ChatRestriction.SEND_MEDIA],
                until=datetime.now() + timedelta(minutes=5))

            # Unban the user
            await client.set_participant_restrictions(chat, user, [])

        .. seealso::

            :meth:`telethon.types.Participant.set_restrictions`
        """
        await set_participant_restrictions(
            self, chat, participant, restrictions, until=until
        )

    async def sign_in(self, token: LoginToken, code: str) -> User | PasswordToken:
        """
        Sign in to a user account.

        :param token:
            The login token returned from :meth:`request_login_code`.

        :param code:
            The login code sent by Telegram to a previously-authorized device.
            This should be a short string of digits.

        :return:
            The user corresponding to :term:`yourself`, or a password token if the account has 2FA enabled.

        .. rubric:: Example

        .. code-block:: python

            from telethon.types import PasswordToken

            login_token = await client.request_login_code('+1 23 456')
            user_or_token = await client.sign_in(login_token, input('code: '))

            if isinstance(password_token, PasswordToken):
                user = await client.check_password(password_token, '1-L0V3+T3l3th0n')

        .. seealso::

            :meth:`check_password`, the next step if the account has 2FA enabled.
        """
        return await sign_in(self, token, code)

    async def sign_out(self) -> None:
        """
        Sign out, revoking the authorization of the current :term:`session`.

        .. rubric:: Example

        .. code-block:: python

            await client.sign_out()  # turn off the lights
            await client.disconnect()  # shut the door
        """
        await sign_out(self)

    async def unpin_message(
        self, chat: Peer | PeerRef, /, message_id: int | Literal["all"]
    ) -> None:
        """
        Unpin one or all messages from the top.

        :param chat:
            The :term:`peer` where the message pinned message is.

        :param message_id:
            The identifier of the message to unpin, or ``'all'`` to unpin them all.

        .. rubric:: Example

        .. code-block:: python

            # Unpin all messages
            await client.unpin_message(chat, 'all')
        """
        await unpin_message(self, chat, message_id)

    # End partially @generated

    @property
    def connected(self) -> bool:
        """
        :data:`True` if :meth:`connect` has been called previously.

        This property will be set back to :data:`False` after calling :meth:`disconnect`.

        This property does *not* check whether the connection is alive.
        The only way to check if the connection still works is to make a request.
        """
        return connected(self)

    def _build_message_map(
        self,
        result: abcs.Updates,
        peer: Optional[PeerRef],
    ) -> MessageMap:
        return build_message_map(self, result, peer)

    async def _upload(
        self, fd: str | Path | InFileLike, size: Optional[int], name: Optional[str]
    ) -> tuple[abcs.InputFile, str]:
        return await upload(self, fd, size, name)

    async def __call__(self, request: Request[Return]) -> Return:
        return await invoke_request(self, request)

    async def __aenter__(self) -> Self:
        await connect(self)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await disconnect(self)
