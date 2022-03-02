import asyncio
import functools
import inspect
import typing
import logging

from . import (
    account, auth, bots, chats, dialogs, downloads, messageparse, messages,
    telegrambaseclient, updates, uploads, users
)
from .. import version, _tl
from ..types import _custom
from .._events.base import EventBuilder
from .._misc import enums


def forward_call(to_func):
    def decorator(from_func):
        return functools.wraps(from_func)(to_func)
    return decorator


class TelegramClient:
    """
    Arguments
        session (`str` | `telethon.sessions.abstract.Session`, `None`):
            The file name of the session file to be used if a string is
            given (it may be a full path), or the Session instance to be
            used otherwise. If it's `None`, the session will not be saved,
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
            The API hash you obtained from https://my.telegram.org.

        connection (`str`, optional):
            The connection mode to be used when creating a new connection
            to the servers. The available modes are:

            * ``'full'``
            * ``'intermediate'``
            * ``'abridged'``
            * ``'obfuscated'``
            * ``'http'``

            Defaults to `telethon.network.connection.tcpfull.ConnectionTcpFull`.

        use_ipv6 (`bool`, optional):
            Whether to connect to the servers through IPv6 or not.
            By default this is `False` as IPv6 support is not
            too widespread yet.

        proxy (`tuple` | `list` | `dict`, optional):
            An iterable consisting of the proxy info. If `connection` is
            one of `MTProxy`, then it should contain MTProxy credentials:
            ``('hostname', port, 'secret')``. Otherwise, it's meant to store
            function parameters for PySocks, like ``(type, 'hostname', port)``.
            See https://github.com/Anorov/PySocks#usage-1 for more.

        local_addr (`str` | `tuple`, optional):
            Local host address (and port, optionally) used to bind the socket to locally.
            You only need to use this if you have multiple network cards and
            want to use a specific one.

        timeout (`int` | `float`, optional):
            The timeout in seconds to be used when connecting.
            This is **not** the timeout to be used when ``await``'ing for
            invoked requests, and you should use ``asyncio.wait`` or
            ``asyncio.wait_for`` for that.

        request_retries (`int` | `None`, optional):
            How many times a request should be retried. Request are retried
            when Telegram is having internal issues (due to either
            ``errors.ServerError`` or ``errors.RpcCallFailError``),
            when there is a ``errors.FloodWaitError`` less than
            `flood_sleep_threshold`, or when there's a migrate error.

            May take a negative or `None` value for infinite retries, but
            this is not recommended, since some requests can always trigger
            a call fail (such as searching for messages).

        connection_retries (`int` | `None`, optional):
            How many times the reconnection should retry, either on the
            initial connection or when Telegram disconnects us. May be
            set to a negative or `None` value for infinite retries, but
            this is not recommended, since the program can get stuck in an
            infinite loop.

        retry_delay (`int` | `float`, optional):
            The delay in seconds to sleep between automatic reconnections.

        auto_reconnect (`bool`, optional):
            Whether reconnection should be retried `connection_retries`
            times automatically if Telegram disconnects us or not.

        sequential_updates (`bool`, optional):
            By default every incoming update will create a new task, so
            you can handle several updates in parallel. Some scripts need
            the order in which updates are processed to be sequential, and
            this setting allows them to do so.

            If set to `True`, incoming updates will be put in a queue
            and processed sequentially. This means your event handlers
            should *not* perform long-running operations since new
            updates are put inside of an unbounded queue.

        flood_sleep_threshold (`int` | `float`, optional):
            The threshold below which the library should automatically
            sleep on flood wait and slow mode wait errors (inclusive). For instance, if a
            ``FloodWaitError`` for 17s occurs and `flood_sleep_threshold`
            is 20s, the library will ``sleep`` automatically. If the error
            was for 21s, it would ``raise FloodWaitError`` instead. Values
            larger than a day (like ``float('inf')``) will be changed to a day.

        raise_last_call_error (`bool`, optional):
            When API calls fail in a way that causes Telethon to retry
            automatically, should the RPC error of the last attempt be raised
            instead of a generic ValueError. This is mostly useful for
            detecting when Telegram has internal issues.

        device_model (`str`, optional):
            "Device model" to be sent when creating the initial connection.
            Defaults to 'PC (n)bit' derived from ``platform.uname().machine``, or its direct value if unknown.

        system_version (`str`, optional):
            "System version" to be sent when creating the initial connection.
            Defaults to ``platform.uname().release`` stripped of everything ahead of -.

        app_version (`str`, optional):
            "App version" to be sent when creating the initial connection.
            Defaults to `telethon.version.__version__`.

        lang_code (`str`, optional):
            "Language code" to be sent when creating the initial connection.
            Defaults to ``'en'``.

        system_lang_code (`str`, optional):
            "System lang code"  to be sent when creating the initial connection.
            Defaults to `lang_code`.

        base_logger (`str` | `logging.Logger`, optional):
            Base logger name or instance to use.
            If a `str` is given, it'll be passed to `logging.getLogger()`. If a
            `logging.Logger` is given, it'll be used directly. If something
            else or nothing is given, the default logger will be used.

        receive_updates (`bool`, optional):
            Whether the client will receive updates or not. By default, updates
            will be received from Telegram as they occur.

            Turning this off means that Telegram will not send updates at all
            so event handlers and QR login will not work. However, certain
            scripts don't need updates, so this will reduce the amount of
            bandwidth used.
    """

    # region Account

    @forward_call(account.takeout)
    def takeout(
            self: 'TelegramClient',
            *,
            contacts: bool = None,
            users: bool = None,
            chats: bool = None,
            megagroups: bool = None,
            channels: bool = None,
            files: bool = None,
            max_file_size: bool = None) -> 'TelegramClient':
        """
        Returns a context-manager which calls `TelegramClient.begin_takeout`
        on enter and `TelegramClient.end_takeout` on exit. The same errors
        and conditions apply.

        This is useful for the common case of not wanting the takeout to
        persist (although it still might if a disconnection occurs before it
        can be ended).

        Example
            .. code-block:: python

                async with client.takeout():
                    async for message in client.get_messages(chat, wait_time=0):
                        ...  # Do something with the message
        """

    @forward_call(account.begin_takeout)
    def begin_takeout(
            self: 'TelegramClient',
            *,
            contacts: bool = None,
            users: bool = None,
            chats: bool = None,
            megagroups: bool = None,
            channels: bool = None,
            files: bool = None,
            max_file_size: bool = None) -> 'TelegramClient':
        """
        Begin a takeout session. All subsequent requests made by the client
        will be behind a takeout session. The takeout session will persist
        in the session file, until `TelegramClient.end_takeout` is used.

        When the takeout session is enabled, some requests will have lower
        flood limits. This is useful if you want to export the data from
        conversations or mass-download media, since the rate limits will
        be lower. Only some requests will be affected, and you will need
        to adjust the `wait_time` of methods like `client.get_messages
        <telethon.client.messages.MessageMethods.get_messages>`.

        By default, all parameters are `None`, and you need to enable those
        you plan to use by setting them to either `True` or `False`.

        You should ``except errors.TakeoutInitDelayError as e``, since this
        exception will raise depending on the condition of the session. You
        can then access ``e.seconds`` to know how long you should wait for
        before calling the method again.

        If you want to ignore the currently-active takeout session in a task,
        toggle the following context variable:

        .. code-block:: python

            telethon.ignore_takeout.set(True)

        An error occurs if ``TelegramClient.takeout_active`` was already ``True``.

        Arguments
            contacts (`bool`):
                Set to `True` if you plan on downloading contacts.

            users (`bool`):
                Set to `True` if you plan on downloading information
                from users and their private conversations with you.

            chats (`bool`):
                Set to `True` if you plan on downloading information
                from small group chats, such as messages and media.

            megagroups (`bool`):
                Set to `True` if you plan on downloading information
                from megagroups (channels), such as messages and media.

            channels (`bool`):
                Set to `True` if you plan on downloading information
                from broadcast channels, such as messages and media.

            files (`bool`):
                Set to `True` if you plan on downloading media and
                you don't only wish to export messages.

            max_file_size (`int`):
                The maximum file size, in bytes, that you plan
                to download for each message with media.

        Example
            .. code-block:: python

                from telethon import errors

                try:
                    await client.begin_takeout()

                    await client.get_messages('me')  # wrapped through takeout (less limits)

                    async for message in client.get_messages(chat, wait_time=0):
                        ...  # Do something with the message

                    await client.end_takeout(success=True)

                except errors.TakeoutInitDelayError as e:
                    print('Must wait', e.seconds, 'before takeout')

                except Exception:
                    await client.end_takeout(success=False)
        """

    @property
    def takeout_active(self: 'TelegramClient') -> bool:
        return account.takeout_active(self)

    @forward_call(account.end_takeout)
    async def end_takeout(self: 'TelegramClient', *, success: bool) -> bool:
        """
        Finishes the current takeout session.

        Arguments
            success (`bool`):
                Whether the takeout completed successfully or not.

        Returns
            `True` if the operation was successful, `False` otherwise.

        Example
            .. code-block:: python

                await client.end_takeout(success=False)
        """

    # endregion Account

    # region Auth

    @forward_call(auth.start)
    def start(
            self: 'TelegramClient',
            *,
            phone: typing.Callable[[], str] = lambda: input('Please enter your phone (or bot token): '),
            password: typing.Callable[[], str] = lambda: getpass.getpass('Please enter your password: '),
            bot_token: str = None,
            code_callback: typing.Callable[[], typing.Union[str, int]] = None,
            first_name: str = 'New User',
            last_name: str = '',
            max_attempts: int = 3) -> 'TelegramClient':
        """
        Starts the client (connects and logs in if necessary).

        By default, this method will be interactive (asking for
        user input if needed), and will handle 2FA if enabled too.

        If the phone doesn't belong to an existing account (and will hence
        `sign_up` for a new one),  **you are agreeing to Telegram's
        Terms of Service. This is required and your account
        will be banned otherwise.** See https://telegram.org/tos
        and https://core.telegram.org/api/terms.

        Even though this method is not marked as ``async``, you still need to
        ``await`` its result for it to do anything useful.

        Arguments
            phone (`str` | `int` | `callable`):
                The phone (or callable without arguments to get it)
                to which the code will be sent. If a bot-token-like
                string is given, it will be used as such instead.
                The argument may be a coroutine.

            password (`str`, `callable`, optional):
                The password for 2 Factor Authentication (2FA).
                This is only required if it is enabled in your account.
                The argument may be a coroutine.

            bot_token (`str`):
                Bot Token obtained by `@BotFather <https://t.me/BotFather>`_
                to log in as a bot. Cannot be specified with ``phone`` (only
                one of either allowed).

            code_callback (`callable`, optional):
                A callable that will be used to retrieve the Telegram
                login code. Defaults to `input()`.
                The argument may be a coroutine.

            first_name (`str`, optional):
                The first name to be used if signing up. This has no
                effect if the account already exists and you sign in.

            last_name (`str`, optional):
                Similar to the first name, but for the last. Optional.

            max_attempts (`int`, optional):
                How many times the code/password callback should be
                retried or switching between signing in and signing up.

        Returns
            This `TelegramClient`, so initialization
            can be chained with ``.start()``.

        Example
            .. code-block:: python

                client = TelegramClient('anon', api_id, api_hash)

                # Starting as a bot account
                await client.start(bot_token=bot_token)

                # Starting as a user account
                await client.start(phone)
                # Please enter the code you received: 12345
                # Please enter your password: *******
                # (You are now logged in)

                # Starting using a context manager (note the lack of await):
                async with client.start():
                    pass
        """

    @forward_call(auth.sign_in)
    async def sign_in(
            self: 'TelegramClient',
            *,
            code: typing.Union[str, int] = None,
            password: str = None,
            bot_token: str = None) -> 'typing.Union[_tl.User, _tl.auth.SentCode]':
        """
        Logs in to Telegram to an existing user or bot account.

        You should only use this if you are not authorized yet.

        .. note::

            In most cases, you should simply use `start()` and not this method.

        Arguments
            code (`str` | `int`):
                The code that Telegram sent.

                To login to a user account, you must use `client.send_code_request` first.

                The code will expire immediately if you send it through the application itself
                as a safety measure.

            password (`str`):
                2FA password, should be used if a previous call raised
                ``SessionPasswordNeededError``.

            bot_token (`str`):
                Used to sign in as a bot. Not all requests will be available.
                This should be the hash the `@BotFather <https://t.me/BotFather>`_
                gave you.

                You do not need to call `client.send_code_request` to login to a bot account.

        Returns
            The signed in `User`, if the method did not fail.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                await client.send_code_request(phone)  # send code

                code = input('enter code: ')
                await client.sign_in(code=code)
        """

    @forward_call(auth.sign_up)
    async def sign_up(
            self: 'TelegramClient',
            first_name: str,
            last_name: str = '',
            *,
            code: typing.Union[str, int]) -> '_tl.User':
        """
        Signs up to Telegram as a new user account.

        Use this if you don't have an account yet.

        You must call `send_code_request` first.

        .. important::

            When creating a new account, you must be sure to show the Terms of Service
            to the user, and only after they approve, the code can accept the Terms of
            Service. If not, they must be declined, in which case the account **will be
            deleted**.

            Make sure to use `client.get_tos` to fetch the Terms of Service, and to
            use `tos.accept()` or `tos.decline()` after the user selects an option.

        Arguments
            first_name (`str`):
                The first name to be used by the new account.

            last_name (`str`, optional)
                Optional last name.

            code (`str` | `int`):
                The code sent by Telegram

        Returns
            The new created :tl:`User`.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                await client.send_code_request(phone)

                code = input('enter code: ')
                await client.sign_up('Anna', 'Banana', code=code)

                # IMPORTANT: you MUST retrieve the Terms of Service and accept
                # them, or Telegram has every right to delete the account.
                tos = await client.get_tos()
                print(tos.html)

                if code('accept (y/n)?: ') == 'y':
                    await tos.accept()
                else:
                    await tos.decline()  # deletes the account!
        """

    @forward_call(auth.send_code_request)
    async def send_code_request(
            self: 'TelegramClient',
            phone: str) -> 'SentCode':
        """
        Sends the Telegram code needed to login to the given phone number.

        Arguments
            phone (`str` | `int`):
                The phone to which the code will be sent.

        Returns
            An instance of `SentCode`.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                sent = await client.send_code_request(phone)
                print(sent.type)

                # Wait before resending sent.next_type, if any
                if sent.next_type:
                    await asyncio.sleep(sent.timeout or 0)
                    resent = await client.send_code_request(phone)
                    print(sent.type)

                # Checking the code locally
                code = input('Enter code: ')
                print('Code looks OK:', resent.check(code))
        """

    @forward_call(auth.qr_login)
    def qr_login(self: 'TelegramClient', ignored_ids: typing.List[int] = None) -> _custom.QrLogin:
        """
        Initiates the QR login procedure.

        Note that you must be connected before invoking this, as with any
        other request.

        It is up to the caller to decide how to present the code to the user,
        whether it's the URL, using the token bytes directly, or generating
        a QR code and displaying it by other means.

        See the documentation for `QrLogin` to see how to proceed after this.

        Note that the login completes once the context manager exits,
        not after the ``wait`` method returns.

        Arguments
            ignored_ids (List[`int`]):
                List of already logged-in session IDs, to prevent logging in
                twice with the same user.

        Returns
            An instance of `QrLogin`.

        Example
            .. code-block:: python

                def display_url_as_qr(url):
                    pass  # do whatever to show url as a qr to the user

                async with client.qr_login() as qr_login:
                    display_url_as_qr(qr_login.url)

                    # Important! You need to wait for the login to complete!
                    # If the context manager exits before the user logs in, the client won't be logged in.
                    try:
                        user = await qr_login.wait()
                        print('Welcome,', user.first_name)
                    except asyncio.TimeoutError:
                        print('User did not login in time')
        """

    @forward_call(auth.log_out)
    async def log_out(self: 'TelegramClient') -> bool:
        """
        Logs out Telegram and deletes the current ``*.session`` file.

        Returns
            `True` if the operation was successful.

        Example
            .. code-block:: python

                # Note: you will need to login again!
                await client.log_out()
        """

    @forward_call(auth.edit_2fa)
    async def edit_2fa(
            self: 'TelegramClient',
            current_password: str = None,
            new_password: str = None,
            *,
            hint: str = '',
            email: str = None,
            email_code_callback: typing.Callable[[int], str] = None) -> bool:
        """
        Changes the 2FA settings of the logged in user.

        Review carefully the parameter explanations before using this method.

        Note that this method may be *incredibly* slow depending on the
        prime numbers that must be used during the process to make sure
        that everything is safe.

        Has no effect if both current and new password are omitted.

        Arguments
            current_password (`str`, optional):
                The current password, to authorize changing to ``new_password``.
                Must be set if changing existing 2FA settings.
                Must **not** be set if 2FA is currently disabled.
                Passing this by itself will remove 2FA (if correct).

            new_password (`str`, optional):
                The password to set as 2FA.
                If 2FA was already enabled, ``current_password`` **must** be set.
                Leaving this blank or `None` will remove the password.

            hint (`str`, optional):
                Hint to be displayed by Telegram when it asks for 2FA.
                Leaving unspecified is highly discouraged.
                Has no effect if ``new_password`` is not set.

            email (`str`, optional):
                Recovery and verification email. If present, you must also
                set `email_code_callback`, else it raises ``ValueError``.

            email_code_callback (`callable`, optional):
                If an email is provided, a callback that returns the code sent
                to it must also be set. This callback may be asynchronous.
                It should return a string with the code. The length of the
                code will be passed to the callback as an input parameter.

                If the callback returns an invalid code, it will raise
                ``CodeInvalidError``.

        Returns
            `True` if successful, `False` otherwise.

        Example
            .. code-block:: python

                # Setting a password for your account which didn't have
                await client.edit_2fa(new_password='I_<3_Telethon')

                # Removing the password
                await client.edit_2fa(current_password='I_<3_Telethon')
        """

    @forward_call(auth.get_tos)
    async def get_tos(self: 'TelegramClient') -> '_custom.TermsOfService':
        """
        Fetch `Telegram's Terms of Service`_, which every user must accept in order to use
        Telegram, or they must otherwise `delete their account`_.

        This method **must** be called after sign up, and **should** be called again
        after it expires (at the risk of having the account terminated otherwise).

        See the documentation of `TermsOfService` for more information.

        The library cannot automate this process because the user must read the Terms of Service.
        Automating its usage without reading the terms would be done at the developer's own risk.

        Example
            .. code-block:: python

                # Fetch the ToS, forever (this could be a separate task, for example)
                while True:
                    tos = await client.get_tos()

                    if tos:
                        # There's an update or they must be accepted (you could show a popup)
                        print(tos.html)
                        if code('accept (y/n)?: ') == 'y':
                            await tos.accept()
                        else:
                            await tos.decline()  # deletes the account!

                    # after tos.timeout expires, the method should be called again!
                    await asyncio.sleep(tos.timeout)

        _Telegram's Terms of Service: https://telegram.org/tos
        _delete their account: https://core.telegram.org/api/config#terms-of-service
        """

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()

    # endregion Auth

    # region Bots

    @forward_call(bots.inline_query)
    async def inline_query(
            self: 'TelegramClient',
            bot: 'hints.DialogLike',
            query: str,
            *,
            dialog: 'hints.DialogLike' = None,
            offset: str = None,
            geo_point: '_tl.GeoPoint' = None) -> _custom.InlineResults:
        """
        Makes an inline query to the specified bot (``@vote New Poll``).

        Arguments
            bot (`entity`):
                The bot user to which the inline query should be made.

            query (`str`):
                The query that should be made to the bot.

            dialog (`entity`, optional):
                The dialog where the inline query is being made from. Certain
                bots use this to display different results depending on where
                it's used, such as private chats, groups or channels.

                If specified, it will also be the default dialog where the
                message will be sent after clicked. Otherwise, the "empty
                peer" will be used, which some bots may not handle correctly.

            offset (`str`, optional):
                The string offset to use for the bot.

            geo_point (:tl:`GeoPoint`, optional)
                The geo point location information to send to the bot
                for localised results. Available under some bots.

        Raises
            If the bot does not respond to the inline query in time,
            `asyncio.TimeoutError` is raised. The timeout is decided by Telegram.

        Returns
            A list of `_custom.InlineResult
            <telethon.tl._custom.inlineresult.InlineResult>`.

        Example
            .. code-block:: python

                # Make an inline query to @like
                results = await client.inline_query('like', 'Do you like Telethon?')

                # Send the first result to some chat
                message = await results[0].click('TelethonOffTopic')
        """

    # endregion Bots

    # region Chats

    @forward_call(chats.get_participants)
    def get_participants(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            limit: float = (),
            *,
            search: str = '',
            filter: typing.Union[str, enums.Participant] = ()) -> chats._ParticipantsIter:
        """
        Iterator over the participants belonging to the specified chat.

        The order is unspecified.

        Arguments
            chat (`entity`):
                The chat from which to retrieve the participants list.

            limit (`int`):
                Limits amount of participants fetched.

                By default, there is no limit set when using the result as
                an iterator. When using ``await``, the default limit is 1,
                so the method returns a single user.

            search (`str`, optional):
                Look for participants with this string in name/username.

                Note that the search is only compatible with some ``filter``
                when fetching members from a channel or megagroup. This may
                change in the future.

            filter (`str`, optional):
                The filter to be used, if you want e.g. only admins
                Note that you might not have permissions for some filter.
                This has no effect for normal chats or users.

                The available filters are:

                * ``'admin'``
                * ``'bot'``
                * ``'kicked'``
                * ``'banned'``
                * ``'contact'``

        Yields
            The :tl:`User` objects returned by :tl:`GetParticipants`.

        Example
            .. code-block:: python

                # Show all user IDs in a chat
                async for user in client.get_participants(chat):
                    print(user.id)

                # Search by name
                async for user in client.get_participants(chat, search='name'):
                    print(user.username)

                # Filter by admins
                from telethon.tl.types import ChannelParticipantsAdmins
                async for user in client.get_participants(chat, filter=ChannelParticipantsAdmins):
                    print(user.first_name)

                # Get a list of 0 people but print the total amount of participants in the chat
                users = await client.get_participants(chat, limit=0)
                print(users.total)
        """

    @forward_call(chats.get_admin_log)
    def get_admin_log(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            limit: float = (),
            *,
            max_id: int = 0,
            min_id: int = 0,
            search: str = None,
            admins: 'hints.DialogsLike' = None,
            join: bool = None,
            leave: bool = None,
            invite: bool = None,
            restrict: bool = None,
            unrestrict: bool = None,
            ban: bool = None,
            unban: bool = None,
            promote: bool = None,
            demote: bool = None,
            info: bool = None,
            settings: bool = None,
            pinned: bool = None,
            edit: bool = None,
            delete: bool = None,
            group_call: bool = None) -> chats._AdminLogIter:
        """
        Iterator over the admin log for the specified channel.

        The default order is from the most recent event to to the oldest.

        Note that you must be an administrator of it to use this method.

        If none of the filters are present (i.e. they all are `None`),
        *all* event types will be returned. If at least one of them is
        `True`, only those that are true will be returned.

        Arguments
            chat (`entity`):
                The chat from which to get its admin log.

            limit (`int` | `None`, optional):
                Number of events to be retrieved.

                The limit may also be `None`, which would eventually return
                the whole history.

                By default, there is no limit set when using the result as
                an iterator. When using ``await``, the default limit is 1,
                so the method returns the last event.

            max_id (`int`):
                All the events with a higher (newer) ID or equal to this will
                be excluded.

            min_id (`int`):
                All the events with a lower (older) ID or equal to this will
                be excluded.

            search (`str`):
                The string to be used as a search query.

            admins (`entity` | `list`):
                If present, the events will be filtered by these admins
                (or single admin) and only those caused by them will be
                returned.

            join (`bool`):
                If `True`, events for when a user joined will be returned.

            leave (`bool`):
                If `True`, events for when a user leaves will be returned.

            invite (`bool`):
                If `True`, events for when a user joins through an invite
                link will be returned.

            restrict (`bool`):
                If `True`, events with partial restrictions will be
                returned. This is what the API calls "ban".

            unrestrict (`bool`):
                If `True`, events removing restrictions will be returned.
                This is what the API calls "unban".

            ban (`bool`):
                If `True`, events applying or removing all restrictions will
                be returned. This is what the API calls "kick" (restricting
                all permissions removed is a ban, which kicks the user).

            unban (`bool`):
                If `True`, events removing all restrictions will be
                returned. This is what the API calls "unkick".

            promote (`bool`):
                If `True`, events with admin promotions will be returned.

            demote (`bool`):
                If `True`, events with admin demotions will be returned.

            info (`bool`):
                If `True`, events changing the group info will be returned.

            settings (`bool`):
                If `True`, events changing the group settings will be
                returned.

            pinned (`bool`):
                If `True`, events of new pinned messages will be returned.

            edit (`bool`):
                If `True`, events of message edits will be returned.

            delete (`bool`):
                If `True`, events of message deletions will be returned.

            group_call (`bool`):
                If `True`, events related to group calls will be returned.

        Yields
            Instances of `AdminLogEvent <telethon.tl._custom.adminlogevent.AdminLogEvent>`.

        Example
            .. code-block:: python

                async for event in client.get_admin_log(channel):
                    if event.changed_title:
                        print('The title changed from', event.old, 'to', event.new)

                # Get all events of deleted message events which said "heck" and print the last one
                events = await client.get_admin_log(channel, limit=None, search='heck', delete=True)

                # Print the old message before it was deleted
                print(events[-1].old)
        """

    @forward_call(chats.get_profile_photos)
    def get_profile_photos(
            self: 'TelegramClient',
            profile: 'hints.DialogLike',
            limit: int = (),
            *,
            offset: int = 0,
            max_id: int = 0) -> chats._ProfilePhotoIter:
        """
        Iterator over a user's profile photos or a chat's photos.

        The order is from the most recent photo to the oldest.

        Arguments
            profile (`entity`):
                The user or chat profile from which to get the profile photos.

            limit (`int` | `None`, optional):
                Number of photos to be retrieved.

                The limit may also be `None`, which would eventually all
                the photos that are still available.

                By default, there is no limit set when using the result as
                an iterator. When using ``await``, the default limit is 1,
                so the method returns the last profile photo.

            offset (`int`):
                How many photos should be skipped before returning the first one.

            max_id (`int`):
                The maximum ID allowed when fetching photos.

        Yields
            Instances of :tl:`Photo`.

        Example
            .. code-block:: python

                # Download all the profile photos of some user
                async for photo in client.get_profile_photos(user):
                    await client.download_media(photo)

                # Get all the photos of a channel and download the oldest one
                photos = await client.get_profile_photos(channel, limit=None)
                await client.download_media(photos[-1])
        """

    @forward_call(chats.action)
    def action(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            action: 'typing.Union[str, _tl.TypeSendMessageAction]',
            *,
            delay: float = 4,
            auto_cancel: bool = True) -> 'typing.Union[_ChatAction, typing.Coroutine]':
        """
        Returns a context-manager object to represent a "chat action".

        Chat actions indicate things like "user is typing", "user is
        uploading a photo", etc.

        If the action is ``'cancel'``, you should just ``await`` the result,
        since it makes no sense to use a context-manager for it.

        See the example below for intended usage.

        Arguments
            dialog (`entity`):
                The dialog where the action should be showed in.

            action (`str` | :tl:`SendMessageAction`):
                The action to show. You can either pass a instance of
                :tl:`SendMessageAction` or better, a string used while:

                * ``'typing'``: typing a text message.
                * ``'contact'``: choosing a contact.
                * ``'game'``: playing a game.
                * ``'location'``: choosing a geo location.
                * ``'sticker'``: choosing a sticker.
                * ``'record-audio'``: recording a voice note.
                  You may use ``'record-voice'`` as alias.
                * ``'record-round'``: recording a round video.
                * ``'record-video'``: recording a normal video.
                * ``'audio'``: sending an audio file (voice note or song).
                  You may use ``'voice'`` and ``'song'`` as aliases.
                * ``'round'``: uploading a round video.
                * ``'video'``: uploading a video file.
                * ``'photo'``: uploading a photo.
                * ``'document'``: uploading a document file.
                  You may use ``'file'`` as alias.
                * ``'cancel'``: cancel any pending action in this chat.

                Invalid strings will raise a ``ValueError``.

            delay (`int` | `float`):
                The delay, in seconds, to wait between sending actions.
                For example, if the delay is 5 and it takes 7 seconds to
                do something, three requests will be made at 0s, 5s, and
                7s to cancel the action.

            auto_cancel (`bool`):
                Whether the action should be cancelled once the context
                manager exists or not. The default is `True`, since
                you don't want progress to be shown when it has already
                completed.

        Returns
            Either a context-manager object or a coroutine.

        Example
            .. code-block:: python

                # Type for 2 seconds, then send a message
                async with client.action(chat, 'typing'):
                    await asyncio.sleep(2)
                    await client.send_message(chat, 'Hello world! I type slow ^^')

                # Cancel any previous action
                await client.action(chat, 'cancel')

                # Upload a document, showing its progress (most clients ignore this)
                async with client.action(chat, 'document') as action:
                    await client.send_file(chat, zip_file, progress_callback=action.progress)
        """

    @forward_call(chats.edit_admin)
    async def edit_admin(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            user: 'hints.DialogLike',
            *,
            change_info: bool = None,
            post_messages: bool = None,
            edit_messages: bool = None,
            delete_messages: bool = None,
            ban_users: bool = None,
            invite_users: bool = None,
            pin_messages: bool = None,
            add_admins: bool = None,
            manage_call: bool = None,
            anonymous: bool = None,
            is_admin: bool = None,
            title: str = None) -> _tl.Updates:
        """
        Edits admin permissions for someone in a chat.

        Raises an error if a wrong combination of rights are given
        (e.g. you don't have enough permissions to grant one).

        Unless otherwise stated, permissions will work in channels and megagroups.

        Arguments
            chat (`entity`):
                The chat where the promotion should happen.

            user (`entity`):
                The user to be promoted.

            change_info (`bool`, optional):
                Whether the user will be able to change info.

            post_messages (`bool`, optional):
                Whether the user will be able to post in the channel.
                This will only work in broadcast channels.

            edit_messages (`bool`, optional):
                Whether the user will be able to edit messages in the channel.
                This will only work in broadcast channels.

            delete_messages (`bool`, optional):
                Whether the user will be able to delete messages.

            ban_users (`bool`, optional):
                Whether the user will be able to ban users.

            invite_users (`bool`, optional):
                Whether the user will be able to invite users. Needs some testing.

            pin_messages (`bool`, optional):
                Whether the user will be able to pin messages.

            add_admins (`bool`, optional):
                Whether the user will be able to add admins.

            manage_call (`bool`, optional):
                Whether the user will be able to manage group calls.

            anonymous (`bool`, optional):
                Whether the user will remain anonymous when sending messages.
                The sender of the anonymous messages becomes the group itself.

                .. note::

                    Users may be able to identify the anonymous admin by its
                    _custom title, so additional care is needed when using both
                    ``anonymous`` and _custom titles. For example, if multiple
                    anonymous admins share the same title, users won't be able
                    to distinguish them.

            is_admin (`bool`, optional):
                Whether the user will be an admin in the chat.
                This will only work in small group chats.
                Whether the user will be an admin in the chat. This is the
                only permission available in small group chats, and when
                used in megagroups, all non-explicitly set permissions will
                have this value.

                Essentially, only passing ``is_admin=True`` will grant all
                permissions, but you can still disable those you need.

            title (`str`, optional):
                The _custom title (also known as "rank") to show for this admin.
                This text will be shown instead of the "admin" badge.
                This will only work in channels and megagroups.

                When left unspecified or empty, the default localized "admin"
                badge will be shown.

        Returns
            The resulting :tl:`Updates` object.

        Example
            .. code-block:: python

                # Allowing `user` to pin messages in `chat`
                await client.edit_admin(chat, user, pin_messages=True)

                # Granting all permissions except for `add_admins`
                await client.edit_admin(chat, user, is_admin=True, add_admins=False)
        """

    @forward_call(chats.edit_permissions)
    async def edit_permissions(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            user: 'typing.Optional[hints.DialogLike]' = None,
            until_date: 'hints.DateLike' = None,
            *,
            view_messages: bool = True,
            send_messages: bool = True,
            send_media: bool = True,
            send_stickers: bool = True,
            send_gifs: bool = True,
            send_games: bool = True,
            send_inline: bool = True,
            embed_link_previews: bool = True,
            send_polls: bool = True,
            change_info: bool = True,
            invite_users: bool = True,
            pin_messages: bool = True) -> _tl.Updates:
        """
        Edits user restrictions in a chat.

        Set an argument to `False` to apply a restriction (i.e. remove
        the permission), or omit them to use the default `True` (i.e.
        don't apply a restriction).

        Raises an error if a wrong combination of rights are given
        (e.g. you don't have enough permissions to revoke one).

        By default, each boolean argument is `True`, meaning that it
        is true that the user has access to the default permission
        and may be able to make use of it.

        If you set an argument to `False`, then a restriction is applied
        regardless of the default permissions.

        It is important to note that `True` does *not* mean grant, only
        "don't restrict", and this is where the default permissions come
        in. A user may have not been revoked the ``pin_messages`` permission
        (it is `True`) but they won't be able to use it if the default
        permissions don't allow it either.

        Arguments
            chat (`entity`):
                The chat where the restriction should happen.

            user (`entity`, optional):
                If specified, the permission will be changed for the specific user.
                If left as `None`, the default chat permissions will be updated.

            until_date (`DateLike`, optional):
                When the user will be unbanned.

                If the due date or duration is longer than 366 days or shorter than
                30 seconds, the ban will be forever. Defaults to ``0`` (ban forever).

            view_messages (`bool`, optional):
                Whether the user is able to view messages or not.
                Forbidding someone from viewing messages equals to banning them.
                This will only work if ``user`` is set.

            send_messages (`bool`, optional):
                Whether the user is able to send messages or not.

            send_media (`bool`, optional):
                Whether the user is able to send media or not.

            send_stickers (`bool`, optional):
                Whether the user is able to send stickers or not.

            send_gifs (`bool`, optional):
                Whether the user is able to send animated gifs or not.

            send_games (`bool`, optional):
                Whether the user is able to send games or not.

            send_inline (`bool`, optional):
                Whether the user is able to use inline bots or not.

            embed_link_previews (`bool`, optional):
                Whether the user is able to enable the link preview in the
                messages they send. Note that the user will still be able to
                send messages with links if this permission is removed, but
                these links won't display a link preview.

            send_polls (`bool`, optional):
                Whether the user is able to send polls or not.

            change_info (`bool`, optional):
                Whether the user is able to change info or not.

            invite_users (`bool`, optional):
                Whether the user is able to invite other users or not.

            pin_messages (`bool`, optional):
                Whether the user is able to pin messages or not.

        Returns
            The resulting :tl:`Updates` object.

        Example
            .. code-block:: python

                from datetime import timedelta

                # Banning `user` from `chat` for 1 minute
                await client.edit_permissions(chat, user, timedelta(minutes=1),
                                              view_messages=False)

                # Banning `user` from `chat` forever
                await client.edit_permissions(chat, user, view_messages=False)

                # Kicking someone (ban + un-ban)
                await client.edit_permissions(chat, user, view_messages=False)
                await client.edit_permissions(chat, user)
        """

    @forward_call(chats.kick_participant)
    async def kick_participant(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            user: 'typing.Optional[hints.DialogLike]'
    ):
        """
        Kicks a user from a chat.

        Kicking yourself (``'me'``) will result in leaving the chat.

        .. note::

            Attempting to kick someone who was banned will remove their
            restrictions (and thus unbanning them), since kicking is just
            ban + unban.

        Arguments
            chat (`entity`):
                The chat where the user should be kicked from.

            user (`entity`, optional):
                The user to kick.

        Returns
            Returns the service `Message <telethon.tl._custom.message.Message>`
            produced about a user being kicked, if any.

        Example
            .. code-block:: python

                # Kick some user from some chat, and deleting the service message
                msg = await client.kick_participant(chat, user)
                await msg.delete()

                # Leaving chat
                await client.kick_participant(chat, 'me')
        """

    @forward_call(chats.get_permissions)
    async def get_permissions(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            user: 'hints.DialogLike' = None
    ) -> 'typing.Optional[_custom.ParticipantPermissions]':
        """
        Fetches the permissions of a user in a specific chat or channel or
        get Default Restricted Rights of Chat or Channel.

        .. note::

            This request has to fetch the entire chat for small group chats,
            which can get somewhat expensive, so use of a cache is advised.

        Arguments
            chat (`entity`):
                The chat the user is participant of.

            user (`entity`, optional):
                Target user.

        Returns
            A `ParticipantPermissions <telethon.tl._custom.participantpermissions.ParticipantPermissions>`
            instance. Refer to its documentation to see what properties are
            available.

        Example
            .. code-block:: python

                permissions = await client.get_permissions(chat, user)
                if permissions.is_admin:
                    # do something

                # Get Banned Permissions of Chat
                await client.get_permissions(chat)
        """

    @forward_call(chats.get_stats)
    async def get_stats(
            self: 'TelegramClient',
            chat: 'hints.DialogLike',
            message: 'typing.Union[int, _tl.Message]' = None,
    ):
        """
        Retrieves statistics from the given megagroup or broadcast channel.

        Note that some restrictions apply before being able to fetch statistics,
        in particular the channel must have enough members (for megagroups, this
        requires `at least 500 members`_).

        Arguments
            chat (`entity`):
                The chat from which to get statistics.

            message (`int` | ``Message``, optional):
                The message ID from which to get statistics, if your goal is
                to obtain the statistics of a single message.

        Raises
            If the given chat is not a broadcast channel ormegagroup,
            a `TypeError` is raised.

            If there are not enough members (poorly named) errors such as
            ``telethon.errors.ChatAdminRequiredError`` will appear.

        Returns
            If both ``chat`` and ``message`` were provided, returns
            :tl:`MessageStats`. Otherwise, either :tl:`BroadcastStats` or
            :tl:`MegagroupStats`, depending on whether the input belonged to a
            broadcast channel or megagroup.

        Example
            .. code-block:: python

                # Some megagroup or channel username or ID to fetch
                channel = -100123
                stats = await client.get_stats(channel)
                print('Stats from', stats.period.min_date, 'to', stats.period.max_date, ':')
                print(stats.stringify())

        .. _`at least 500 members`: https://telegram.org/blog/profile-videos-people-nearby-and-more
        """

    # endregion Chats

    # region Dialogs

    @forward_call(dialogs.get_dialogs)
    def get_dialogs(
            self: 'TelegramClient',
            limit: float = (),
            *,
            offset_date: 'hints.DateLike' = None,
            offset_id: int = 0,
            offset_peer: 'hints.DialogLike' = _tl.InputPeerEmpty(),
            ignore_pinned: bool = False,
            ignore_migrated: bool = False,
            folder: int = None,
    ) -> dialogs._DialogsIter:
        """
        Iterator over the dialogs (open conversations/subscribed channels).

        The order is the same as the one seen in official applications
        (first pinned, them from those with the most recent message to
        those with the oldest message).

        Arguments
            limit (`int` | `None`):
                How many dialogs to be retrieved as maximum. Can be set to
                `None` to retrieve all dialogs. Note that this may take
                whole minutes if you have hundreds of dialogs, as Telegram
                will tell the library to slow down through a
                ``FloodWaitError``.

                By default, there is no limit set when using the result as
                an iterator. When using ``await``, the default limit is 1,
                so the method returns the most-recent dialog.

            offset_date (`datetime`, optional):
                The offset date to be used.

            offset_id (`int`, optional):
                The message ID to be used as an offset.

            offset_peer (:tl:`InputPeer`, optional):
                The peer to be used as an offset.

            ignore_pinned (`bool`, optional):
                Whether pinned dialogs should be ignored or not.
                When set to `True`, these won't be yielded at all.

            ignore_migrated (`bool`, optional):
                Whether :tl:`Chat` that have ``migrated_to`` a :tl:`Channel`
                should be included or not. By default all the chats in your
                dialogs are returned, but setting this to `True` will ignore
                (i.e. skip) them in the same way official applications do.

            folder (`int`, optional):
                The folder from which the dialogs should be retrieved.

                If left unspecified, all dialogs (including those from
                folders) will be returned.

                If set to ``0``, all dialogs that don't belong to any
                folder will be returned.

                If set to a folder number like ``1``, only those from
                said folder will be returned.

                By default Telegram assigns the folder ID ``1`` to
                archived chats, so you should use that if you need
                to fetch the archived dialogs.
        Yields
            Instances of `Dialog <telethon.tl._custom.dialog.Dialog>`.

        Example
            .. code-block:: python

                # Print all dialog IDs and the title, nicely formatted
                async for dialog in client.get_dialogs():
                    print('{:>14}: {}'.format(dialog.id, dialog.title))

                # Get all open conversation, print the title of the first
                dialogs = await client.get_dialogs(limit=None)
                first = dialogs[0]
                print(first.title)

                # Use the dialog somewhere else
                await client.send_message(first, 'hi')

                # Getting only non-archived dialogs (both equivalent)
                non_archived = await client.get_dialogs(folder=0, limit=None)

                # Getting only archived dialogs (both equivalent)
                archived = await client.get_dialogs(folder=1, limit=None)
        """

    @forward_call(dialogs.get_drafts)
    def get_drafts(
            self: 'TelegramClient',
            dialog: 'hints.DialogsLike' = None
    ) -> dialogs._DraftsIter:
        """
        Iterator over draft messages.

        The order is unspecified.

        Arguments
            dialog (`hints.DialogsLike`, optional):
                The dialog or dialogs for which to fetch the draft messages.
                If left unspecified, all draft messages will be returned.

        Yields
            Instances of `Draft <telethon.tl._custom.draft.Draft>`.

        Example
            .. code-block:: python

                # Clear all drafts
                async for draft in client.get_drafts():
                    await draft.delete()

                # Getting the drafts with 'bot1' and 'bot2'
                async for draft in client.get_drafts(['bot1', 'bot2']):
                    print(draft.text)

                # Get the draft in your chat
                draft = await client.get_drafts('me')
                print(draft.text)
        """

    @forward_call(dialogs.delete_dialog)
    async def delete_dialog(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            *,
            revoke: bool = False
    ):
        """
        Deletes a dialog (leaves a chat or channel).

        This method can be used as a user and as a bot. However,
        bots will only be able to use it to leave groups and channels
        (trying to delete a private conversation will do nothing).

        See also `Dialog.delete() <telethon.tl._custom.dialog.Dialog.delete>`.

        Arguments
            dialog (entities):
                The dialog to delete. If it's a chat or
                channel, you will leave it. Note that the chat itself
                is not deleted, only the dialog, because you left it.

            revoke (`bool`, optional):
                On private chats, you may revoke the messages from
                the other peer too. By default, it's `False`. Set
                it to `True` to delete the history for both.

                This makes no difference for bot accounts, who can
                only leave groups and channels.

        Returns
            The :tl:`Updates` object that the request produces,
            or nothing for private conversations.

        Example
            .. code-block:: python

                # Deleting the first dialog
                dialogs = await client.get_dialogs(5)
                await client.delete_dialog(dialogs[0])

                # Leaving a channel by username
                await client.delete_dialog('username')
        """

    # endregion Dialogs

    # region Downloads

    @forward_call(downloads.download_profile_photo)
    async def download_profile_photo(
            self: 'TelegramClient',
            profile: 'hints.DialogLike',
            file: 'hints.FileLike' = None,
            *,
            thumb: typing.Union[str, enums.Size] = (),
            progress_callback: 'hints.ProgressCallback' = None) -> typing.Optional[str]:
        """
        Downloads the profile photo from the given user, chat or channel.

        Arguments
            profile (`entity`):
                The profile from which to download its photo.

                .. note::

                    This method expects the full entity (which has the data
                    to download the photo), not an input variant.

                    It's possible that sometimes you can't fetch the entity
                    from its input (since you can get errors like
                    ``ChannelPrivateError``) but you already have it through
                    another call, like getting a forwarded message from it.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.
                If file is the type `bytes`, it will be downloaded in-memory
                as a bytestring (e.g. ``file=bytes``).

            thumb (optional):
                The thumbnail size to download. A different size may be chosen
                if the specified size doesn't exist. The category of the size
                you choose will be respected when possible (e.g. if you
                specify a cropped size, a cropped variant of similar size will
                be preferred over a boxed variant of similar size). Cropped
                images are considered to be smaller than boxed images.

                By default, the largest size (original) is downloaded.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(received bytes, total)``.

        Returns
            `None` if no photo was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.

        Example
            .. code-block:: python

                # Download your own profile photo
                path = await client.download_profile_photo('me')
                print(path)
        """

    @forward_call(downloads.download_media)
    async def download_media(
            self: 'TelegramClient',
            media: 'hints.MessageLike',
            file: 'hints.FileLike' = None,
            *,
            thumb: typing.Union[str, enums.Size] = (),
            progress_callback: 'hints.ProgressCallback' = None) -> typing.Optional[typing.Union[str, bytes]]:
        """
        Downloads the given media from a message object.

        Note that if the download is too slow, you should consider installing
        ``cryptg`` (through ``pip install cryptg``) so that decrypting the
        received data is done in C instead of Python (much faster).

        See also `Message.download_media() <telethon.tl._custom.message.Message.download_media>`.

        Arguments
            media (:tl:`Media`):
                The media that will be downloaded.

            file (`str` | `file`, optional):
                The output file path, directory, or stream-like object.
                If the path exists and is a file, it will be overwritten.
                If file is the type `bytes`, it will be downloaded in-memory
                as a bytestring (e.g. ``file=bytes``).

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(received bytes, total)``.

            thumb (optional):
                The thumbnail size to download. A different size may be chosen
                if the specified size doesn't exist. The category of the size
                you choose will be respected when possible (e.g. if you
                specify a cropped size, a cropped variant of similar size will
                be preferred over a boxed variant of similar size). Cropped
                images are considered to be smaller than boxed images.

                By default, the original media is downloaded.

        Returns
            `None` if no media was provided, or if it was Empty. On success
            the file path is returned since it may differ from the one given.

        Example
            .. code-block:: python

                path = await client.download_media(message)
                await client.download_media(message, filename)
                # or
                path = await message.download_media()
                await message.download_media(filename)

                # Printing download progress
                def callback(current, total):
                    print('Downloaded', current, 'out of', total,
                          'bytes: {:.2%}'.format(current / total))

                await client.download_media(message, progress_callback=callback)
        """

    @forward_call(downloads.iter_download)
    def iter_download(
            self: 'TelegramClient',
            media: 'hints.FileLike',
            *,
            offset: int = 0,
            stride: int = None,
            limit: int = None,
            chunk_size: int = None,
            request_size: int = downloads.MAX_CHUNK_SIZE,
            file_size: int = None,
            dc_id: int = None
    ):
        """
        Iterates over a file download, yielding chunks of the file.

        This method can be used to stream files in a more convenient
        way, since it offers more control (pausing, resuming, etc.)

        .. note::

            Using a value for `offset` or `stride` which is not a multiple
            of the minimum allowed `request_size`, or if `chunk_size` is
            different from `request_size`, the library will need to do a
            bit more work to fetch the data in the way you intend it to.

            You normally shouldn't worry about this.

        Arguments
            file (`hints.FileLike`):
                The file of which contents you want to iterate over.

            offset (`int`, optional):
                The offset in bytes into the file from where the
                download should start. For example, if a file is
                1024KB long and you just want the last 512KB, you
                would use ``offset=512 * 1024``.

            stride (`int`, optional):
                The stride of each chunk (how much the offset should
                advance between reading each chunk). This parameter
                should only be used for more advanced use cases.

                It must be bigger than or equal to the `chunk_size`.

            limit (`int`, optional):
                The limit for how many *chunks* will be yielded at most.

            chunk_size (`int`, optional):
                The maximum size of the chunks that will be yielded.
                Note that the last chunk may be less than this value.
                By default, it equals to `request_size`.

            request_size (`int`, optional):
                How many bytes will be requested to Telegram when more
                data is required. By default, as many bytes as possible
                are requested. If you would like to request data in
                smaller sizes, adjust this parameter.

                Note that values outside the valid range will be clamped,
                and the final value will also be a multiple of the minimum
                allowed size.

            file_size (`int`, optional):
                If the file size is known beforehand, you should set
                this parameter to said value. Depending on the type of
                the input file passed, this may be set automatically.

            dc_id (`int`, optional):
                The data center the library should connect to in order
                to download the file. You shouldn't worry about this.

        Yields

            `bytes` objects representing the chunks of the file if the
            right conditions are met, or `memoryview` objects instead.

        Example
            .. code-block:: python

                # Streaming `media` to an output file
                # After the iteration ends, the sender is cleaned up
                with open('photo.jpg', 'wb') as fd:
                    async for chunk in client.iter_download(media):
                        fd.write(chunk)

                # Fetching only the header of a file (32 bytes)
                # You should manually close the iterator in this case.
                #
                # "stream" is a common name for asynchronous generators,
                # and iter_download will yield `bytes` (chunks of the file).
                stream = client.iter_download(media, request_size=32)
                header = await stream.__anext__()  # "manual" version of `async for`
                await stream.close()
                assert len(header) == 32
        """

    # endregion Downloads

    # region Messages

    @forward_call(messages.get_messages)
    def get_messages(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            limit: float = (),
            *,
            offset_date: 'hints.DateLike' = None,
            offset_id: int = 0,
            max_id: int = 0,
            min_id: int = 0,
            add_offset: int = 0,
            search: str = None,
            filter: 'typing.Union[_tl.TypeMessagesFilter, typing.Type[_tl.TypeMessagesFilter]]' = None,
            from_user: 'hints.DialogLike' = None,
            wait_time: float = None,
            ids: 'typing.Union[int, typing.Sequence[int]]' = None,
            reverse: bool = False,
            reply_to: int = None,
            scheduled: bool = False
    ) -> 'typing.Union[_MessagesIter, _IDsIter]':
        """
        Iterator over the messages for the given chat.

        The default order is from newest to oldest, but this
        behaviour can be changed with the `reverse` parameter.

        If either `search`, `filter` or `from_user` are provided,
        :tl:`messages.Search` will be used instead of :tl:`messages.getHistory`.

        .. note::

            Telegram's flood wait limit for :tl:`GetHistory` seems to
            be around 30 seconds per 10 requests, therefore a sleep of 1
            second is the default for this limit (or above).

        Arguments
            dialog (`entity`):
                The dialog from which to retrieve the message history.

                It may be `None` to perform a global search, or
                to get messages by their ID from no particular chat.
                Note that some of the offsets will not work if this
                is the case.

                Note that if you want to perform a global search,
                you **must** set a non-empty `search` string, a `filter`.
                or `from_user`.

            limit (`int` | `None`, optional):
                Number of messages to be retrieved. Due to limitations with
                the API retrieving more than 3000 messages will take longer
                than half a minute (or even more based on previous calls).

                The limit may also be `None`, which would eventually return
                the whole history.

                By default, there is no limit set when using the result as
                an iterator. When using ``await``, the default limit is 1,
                so the method returns the last message.

            offset_date (`datetime`):
                Offset date (messages *previous* to this date will be
                retrieved). Exclusive.

            offset_id (`int`):
                Offset message ID (only messages *previous* to the given
                ID will be retrieved). Exclusive.

            max_id (`int`):
                All the messages with a higher (newer) ID or equal to this will
                be excluded.

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

            wait_time (`int`):
                Wait time (in seconds) between different
                :tl:`GetHistory`. Use this parameter to avoid hitting
                the ``FloodWaitError`` as needed. If left to `None`, it will
                default to 1 second only if the limit is higher than 3000.

                If the ``ids`` parameter is used, this time will default
                to 10 seconds only if the amount of IDs is higher than 300.

            ids (`int`, `list`):
                A single integer ID (or several IDs) for the message that
                should be returned. This parameter takes precedence over
                the rest (which will be ignored if this is set). This can
                for instance be used to get the message with ID 123 from
                a channel. Note that if the message doesn't exist, `None`
                will appear in its place, so that zipping the list of IDs
                with the messages can match one-to-one.

                .. note::

                    At the time of writing, Telegram will **not** return
                    :tl:`MessageEmpty` for :tl:`InputMessageReplyTo` IDs that
                    failed (i.e. the message is not replying to any, or is
                    replying to a deleted message). This means that it is
                    **not** possible to match messages one-by-one, so be
                    careful if you use non-integers in this parameter.

            reverse (`bool`, optional):
                If set to `True`, the messages will be returned in reverse
                order (from oldest to newest, instead of the default newest
                to oldest). This also means that the meaning of `offset_id`
                and `offset_date` parameters is reversed, although they will
                still be exclusive. `min_id` becomes equivalent to `offset_id`
                instead of being `max_id` as well since messages are returned
                in ascending order.

                You cannot use this if both `dialog` and `ids` are `None`.

            reply_to (`int`, optional):
                If set to a message ID, the messages that reply to this ID
                will be returned. This feature is also known as comments in
                posts of broadcast channels, or viewing threads in groups.

                This feature can only be used in broadcast channels and their
                linked megagroups. Using it in a chat or private conversation
                will result in ``telethon.errors.PeerIdInvalidError`` to occur.

                When using this parameter, the ``filter`` and ``search``
                parameters have no effect, since Telegram's API doesn't
                support searching messages in replies.

                .. note::

                    This feature is used to get replies to a message in the
                    *discussion* group. If the same broadcast channel sends
                    a message and replies to it itself, that reply will not
                    be included in the results.

            scheduled (`bool`, optional):
                If set to `True`, messages which are scheduled will be returned.
                All other parameter will be ignored for this, except `dialog`.

        Yields
            Instances of `Message <telethon.tl._custom.message.Message>`.

        Example
            .. code-block:: python

                # From most-recent to oldest
                async for message in client.get_messages(chat):
                    print(message.id, message.text)

                # From oldest to most-recent
                async for message in client.get_messages(chat, reverse=True):
                    print(message.id, message.text)

                # Filter by sender, and limit to 10
                async for message in client.get_messages(chat, 10, from_user='me'):
                    print(message.text)

                # Server-side search with fuzzy text
                async for message in client.get_messages(chat, search='hello'):
                    print(message.id)

                # Filter by message type:
                from telethon.tl.types import InputMessagesFilterPhotos
                async for message in client.get_messages(chat, filter=InputMessagesFilterPhotos):
                    print(message.photo)

                # Getting comments from a post in a channel:
                async for message in client.get_messages(channel, reply_to=123):
                    print(message.chat.title, message.text)

                # Get 0 photos and print the total to show how many photos there are
                from telethon.tl.types import InputMessagesFilterPhotos
                photos = await client.get_messages(chat, 0, filter=InputMessagesFilterPhotos)
                print(photos.total)

                # Get all the photos in a list
                all_photos = await client.get_messages(chat, None, filter=InputMessagesFilterPhotos)

                # Get the last photo or None if none has been sent yet (same as setting limit 1)
                photo = await client.get_messages(chat, filter=InputMessagesFilterPhotos)

                # Get a single message given an ID:
                message_1337 = await client.get_messages(chat, ids=1337)
        """

    @forward_call(messages.send_message)
    async def send_message(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            message: 'hints.MessageLike' = '',
            *,
            # - Message contents
            # Formatting
            markdown: str = None,
            html: str = None,
            formatting_entities: list = None,
            link_preview: bool = (),
            # Media
            file: 'typing.Optional[hints.FileLike]' = None,
            file_name: str = None,
            mime_type: str = None,
            thumb: str = False,
            force_file: bool = False,
            file_size: int = None,
            # Media attributes
            duration: int = None,
            width: int = None,
            height: int = None,
            title: str = None,
            performer: str = None,
            supports_streaming: bool = False,
            video_note: bool = False,
            voice_note: bool = False,
            waveform: bytes = None,
            # Additional parametrization
            silent: bool = False,
            buttons: list = None,
            ttl: int = None,
            # - Send options
            reply_to: 'typing.Union[int, _tl.Message]' = None,
            clear_draft: bool = False,
            background: bool = None,
            schedule: 'hints.DateLike' = None,
            comment_to: 'typing.Union[int, _tl.Message]' = None,
    ) -> '_tl.Message':
        """
        Sends a Message to the specified user, chat or channel.

        The message can be either a string or a previous Message instance.
        If it's a previous Message instance, the rest of parameters will be ignored.
        If it's not, a Message instance will be constructed, and send_to used.

        Sending a ``/start`` command with a parameter (like ``?start=data``)
        is also done through this method. Simply send ``'/start data'`` to
        the bot.

        See also `Message.respond() <telethon.tl._custom.message.Message.respond>`
        and `Message.reply() <telethon.tl._custom.message.Message.reply>`.

        Arguments
            dialog (`entity`):
                To who will it be sent.

            message (`str` | `Message <telethon.tl._custom.message.Message>`):
                The message to be sent, or another message object to resend.

                The maximum length for a message is 35,000 bytes or 4,096
                characters. Longer messages will not be sliced automatically,
                and you should slice them manually if the text to send is
                longer than said length.

            reply_to (`int` | `Message <telethon.tl._custom.message.Message>`, optional):
                Whether to reply to a message or not. If an integer is provided,
                it should be the ID of the message that it should reply to.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            formatting_entities (`list`, optional):
                A list of message formatting entities. When provided, the ``parse_mode`` is ignored.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`file`, optional):
                Sends a message with a file attached (e.g. a photo,
                video, audio or document). The ``message`` may be empty.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!
                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.

            buttons (`list`, `_custom.Button <telethon.tl._custom.button.Button>`, :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

                All the following limits apply together:

                * There can be 100 buttons at most (any more are ignored).
                * There can be 8 buttons per row at most (more are ignored).
                * The maximum callback data per button is 64 bytes.
                * The maximum data that can be embedded in total is just
                  over 4KB, shared between inline callback data and text.

            silent (`bool`, optional):
                Whether the message should notify people in a broadcast
                channel or not. Defaults to `False`, which means it will
                notify them. Set it to `True` to alter this behaviour.

            background (`bool`, optional):
                Whether the message should be send in background.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the message won't send immediately, and instead
                it will be scheduled to be automatically sent at a later
                time.

            comment_to (`int` | `Message <telethon.tl._custom.message.Message>`, optional):
                Similar to ``reply_to``, but replies in the linked group of a
                broadcast channel instead (effectively leaving a "comment to"
                the specified message).

                This parameter takes precedence over ``reply_to``. If there is
                no linked chat, `telethon.errors.sgIdInvalidError` is raised.

        Returns
            The sent `_custom.Message <telethon.tl._custom.message.Message>`.

        Example
            .. code-block:: python

                # Markdown is the default
                await client.send_message('me', 'Hello **world**!')

                # Default to another parse mode
                from telethon.types import Message
                Message.set_default_parse_mode('html')

                await client.send_message('me', 'Some <b>bold</b> and <i>italic</i> text')
                await client.send_message('me', 'An <a href="https://example.com">URL</a>')
                # code and pre tags also work, but those break the documentation :)
                await client.send_message('me', '<a href="tg://user?id=me">Mentions</a>')

                # Explicit parse mode
                # No parse mode by default (import Message first)
                Message.set_default_parse_mode(None)

                # ...but here I want markdown
                await client.send_message('me', 'Hello, **world**!', parse_mode='md')

                # ...and here I need HTML
                await client.send_message('me', 'Hello, <i>world</i>!', parse_mode='html')

                # If you logged in as a bot account, you can send buttons
                from telethon import events, Button

                @client.on(events.CallbackQuery)
                async def callback(event):
                    await event.edit('Thank you for clicking {}!'.format(event.data))

                # Single inline button
                await client.send_message(chat, 'A single button, with "clk1" as data',
                                          buttons=Button.inline('Click me', b'clk1'))

                # Matrix of inline buttons
                await client.send_message(chat, 'Pick one from this grid', buttons=[
                    [Button.inline('Left'), Button.inline('Right')],
                    [Button.url('Check this site!', 'https://example.com')]
                ])

                # Reply keyboard
                await client.send_message(chat, 'Welcome', buttons=[
                    Button.text('Thanks!', resize=True, single_use=True),
                    Button.request_phone('Send phone'),
                    Button.request_location('Send location')
                ])

                # Forcing replies or clearing buttons.
                await client.send_message(chat, 'Reply to me', buttons=Button.force_reply())
                await client.send_message(chat, 'Bye Keyboard!', buttons=Button.clear())

                # Scheduling a message to be sent after 5 minutes
                from datetime import timedelta
                await client.send_message(chat, 'Hi, future!', schedule=timedelta(minutes=5))
        """

    @forward_call(messages.forward_messages)
    async def forward_messages(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            messages: 'typing.Union[typing.Sequence[hints.MessageIDLike]]',
            from_dialog: 'hints.DialogLike' = None,
            *,
            background: bool = None,
            with_my_score: bool = None,
            silent: bool = None,
            as_album: bool = None,
            schedule: 'hints.DateLike' = None
    ) -> 'typing.Sequence[_tl.Message]':
        """
        Forwards the given messages to the specified dialog.

        If you want to "forward" a message without the forward header
        (the "forwarded from" text), you should use `send_message` with
        the original message instead. This will send a copy of it.

        See also `Message.forward_to() <telethon.tl._custom.message.Message.forward_to>`.

        Arguments
            dialog (`entity`):
                The target dialog where the message(s) will be forwarded.

            messages (`list`):
                The messages to forward, or their integer IDs.

            from_dialog (`entity`):
                If the given messages are integer IDs and not instances
                of the ``Message`` class, this *must* be specified in
                order for the forward to work. This parameter indicates
                the source dialog from which the messages should be forwarded.

            silent (`bool`, optional):
                Whether the message should notify people with sound or not.
                Defaults to `False` (send with a notification sound unless
                the person has the chat muted). Set it to `True` to alter
                this behaviour.

            background (`bool`, optional):
                Whether the message should be forwarded in background.

            with_my_score (`bool`, optional):
                Whether forwarded should contain your game score.

            as_album (`bool`, optional):
                This flag no longer has any effect.

            schedule (`hints.DateLike`, optional):
                If set, the message(s) won't forward immediately, and
                instead they will be scheduled to be automatically sent
                at a later time.

        Returns
            The list of forwarded `Message <telethon.tl._custom.message.Message>`,
            or a single one if a list wasn't provided as input.

            Note that if all messages are invalid (i.e. deleted) the call
            will fail with ``MessageIdInvalidError``. If only some are
            invalid, the list will have `None` instead of those messages.

        Example
            .. code-block:: python

                # a single one
                await client.forward_messages(chat, message)
                # or
                await client.forward_messages(chat, message_id, from_chat)
                # or
                await message.forward_to(chat)

                # multiple
                await client.forward_messages(chat, messages)
                # or
                await client.forward_messages(chat, message_ids, from_chat)

                # Forwarding as a copy
                await client.send_message(chat, message)
        """

    @forward_call(messages.edit_message)
    async def edit_message(
            self: 'TelegramClient',
            dialog: 'typing.Union[hints.DialogLike, _tl.Message]',
            message: 'hints.MessageLike',
            text: str = None,
            *,
            parse_mode: str = (),
            attributes: 'typing.Sequence[_tl.TypeDocumentAttribute]' = None,
            formatting_entities: typing.Optional[typing.List[_tl.TypeMessageEntity]] = None,
            link_preview: bool = True,
            file: 'hints.FileLike' = None,
            thumb: 'hints.FileLike' = None,
            force_document: bool = False,
            buttons: 'hints.MarkupLike' = None,
            supports_streaming: bool = False,
            schedule: 'hints.DateLike' = None
    ) -> '_tl.Message':
        """
        Edits the given message to change its text or media.

        See also `Message.edit() <telethon.tl._custom.message.Message.edit>`.

        Arguments
            dialog (`entity` | `Message <telethon.tl._custom.message.Message>`):
                From which chat to edit the message. This can also be
                the message to be edited, and the dialog will be inferred
                from it, so the next parameter will be assumed to be the
                message text.

                You may also pass a :tl:`InputBotInlineMessageID`,
                which is the only way to edit messages that were sent
                after the user selects an inline query result.

            message (`int` | `Message <telethon.tl._custom.message.Message>` | `str`):
                The ID of the message (or `Message
                <telethon.tl._custom.message.Message>` itself) to be edited.
                If the `dialog` was a `Message
                <telethon.tl._custom.message.Message>`, then this message
                will be treated as the new text.

            text (`str`, optional):
                The new text of the message. Does nothing if the `dialog`
                was a `Message <telethon.tl._custom.message.Message>`.

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            formatting_entities (`list`, optional):
                A list of message formatting entities. When provided, the ``parse_mode`` is ignored.

            link_preview (`bool`, optional):
                Should the link preview be shown?

            file (`str` | `bytes` | `file` | `media`, optional):
                The file object that should replace the existing media
                in the message.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!
                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.

            force_document (`bool`, optional):
                Whether to send the given file as a document or not.

            buttons (`list`, `_custom.Button <telethon.tl._custom.button.Button>`, :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the message won't be edited immediately, and instead
                it will be scheduled to be automatically edited at a later
                time.

                Note that this parameter will have no effect if you are
                trying to edit a message that was sent via inline bots.

        Returns
            The edited `Message <telethon.tl._custom.message.Message>`,
            unless `dialog` was a :tl:`InputBotInlineMessageID` in which
            case this method returns a boolean.

        Raises
            ``MessageAuthorRequiredError`` if you're not the author of the
            message but tried editing it anyway.

            ``MessageNotModifiedError`` if the contents of the message were
            not modified at all.

            ``MessageIdInvalidError`` if the ID of the message is invalid
            (the ID itself may be correct, but the message with that ID
            cannot be edited). For example, when trying to edit messages
            with a reply markup (or clear markup) this error will be raised.

        Example
            .. code-block:: python

                message = await client.send_message(chat, 'hello')

                await client.edit_message(chat, message, 'hello!')
                # or
                await client.edit_message(chat, message.id, 'hello!!')
                # or
                await message.edit('hello!!!')
        """

    @forward_call(messages.delete_messages)
    async def delete_messages(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            messages: 'typing.Union[typing.Sequence[hints.MessageIDLike]]',
            *,
            revoke: bool = True) -> 'typing.Sequence[_tl.messages.AffectedMessages]':
        """
        Deletes the given messages, optionally "for everyone".

        See also `Message.delete() <telethon.tl._custom.message.Message.delete>`.

        .. warning::

            This method does **not** validate that the message IDs belong
            to the chat that you passed! It's possible for the method to
            delete messages from different private chats and small group
            chats at once, so make sure to pass the right IDs.

        Arguments
            dialog (`entity`):
                From who the message will be deleted. This can actually
                be `None` for normal chats, but **must** be present
                for channels and megagroups.

            messages (`list`):
                The messages to delete, or their integer IDs.

            revoke (`bool`, optional):
                Whether the message should be deleted for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will delete the message for everyone.

                `Since 24 March 2019
                <https://telegram.org/blog/unsend-privacy-emoji>`_, you can
                also revoke messages of any age (i.e. messages sent long in
                the past) the *other* person sent in private conversations
                (and of course your messages too).

                Disabling this has no effect on channels or megagroups,
                since it will unconditionally delete the message for everyone.

        Returns
            A list of :tl:`AffectedMessages`, each item being the result
            for the delete calls of the messages in chunks of 100 each.

        Example
            .. code-block:: python

                await client.delete_messages(chat, messages)
        """

    @forward_call(messages.mark_read)
    async def mark_read(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            message: 'hints.MessageIDLike' = None,
            *,
            clear_mentions: bool = False) -> bool:
        """
        Marks messages as read and optionally clears mentions.

        This effectively marks a message as read (or more than one) in the
        given conversation.

        If no message or maximum ID is provided, all messages will be
        marked as read.

        If a message or maximum ID is provided, all the messages up to and
        including such ID will be marked as read (for all messages whose ID
        ≤ max_id).

        See also `Message.mark_read() <telethon.tl._custom.message.Message.mark_read>`.

        Arguments
            dialog (`entity`):
                The chat where these messages are located.

            message (`Message <telethon.tl._custom.message.Message>`):
                The last (most-recent) message which was read, or its ID.
                This is only useful if you want to mark a chat as partially read.

            max_id (`int`):
                Until which message should the read acknowledge be sent for.
                This has priority over the ``message`` parameter.

            clear_mentions (`bool`):
                Whether the mention badge should be cleared (so that
                there are no more mentions) or not for the given entity.

                If no message is provided, this will be the only action
                taken.

        Example
            .. code-block:: python

                # using a Message object
                await client.mark_read(chat, message)
                # ...or using the int ID of a Message
                await client.mark_read(chat, message_id)
                # ...or passing a list of messages to mark as read
                await client.mark_read(chat, messages)
        """

    @forward_call(messages.pin_message)
    async def pin_message(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            message: 'typing.Optional[hints.MessageIDLike]',
            *,
            notify: bool = False,
            pm_oneside: bool = False
    ):
        """
        Pins a message in a chat.

        The default behaviour is to *not* notify members, unlike the
        official applications.

        See also `Message.pin() <telethon.tl._custom.message.Message.pin>`.

        Arguments
            dialog (`entity`):
                The chat where the message should be pinned.

            message (`int` | `Message <telethon.tl._custom.message.Message>`):
                The message or the message ID to pin. If it's
                `None`, all messages will be unpinned instead.

            notify (`bool`, optional):
                Whether the pin should notify people or not.

            pm_oneside (`bool`, optional):
                Whether the message should be pinned for everyone or not.
                By default it has the opposite behaviour of official clients,
                and it will pin the message for both sides, in private chats.

        Example
            .. code-block:: python

                # Send and pin a message to annoy everyone
                message = await client.send_message(chat, 'Pinotifying is fun!')
                await client.pin_message(chat, message, notify=True)
        """

    @forward_call(messages.unpin_message)
    async def unpin_message(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            message: 'typing.Optional[hints.MessageIDLike]' = None,
            *,
            notify: bool = False
    ):
        """
        Unpins a message in a chat.

        If no message ID is specified, all pinned messages will be unpinned.

        See also `Message.unpin() <telethon.tl._custom.message.Message.unpin>`.

        Arguments
            dialog (`entity`):
                The dialog where the message should be pinned.

            message (`int` | `Message <telethon.tl._custom.message.Message>`):
                The message or the message ID to unpin. If it's
                `None`, all messages will be unpinned instead.

        Example
            .. code-block:: python

                # Unpin all messages from a chat
                await client.unpin_message(chat)
        """

    # endregion Messages

    # region Base

    # Current TelegramClient version
    __version__ = version.__version__

    def __init__(
            self: 'TelegramClient',
            session: 'typing.Union[str, Session]',
            api_id: int,
            api_hash: str,
            *,
            # Logging.
            base_logger: typing.Union[str, logging.Logger] = None,
            # Connection parameters.
            use_ipv6: bool = False,
            proxy: typing.Union[tuple, dict] = None,
            local_addr: typing.Union[str, tuple] = None,
            device_model: str = None,
            system_version: str = None,
            app_version: str = None,
            lang_code: str = 'en',
            system_lang_code: str = 'en',
            # Nice-to-have.
            auto_reconnect: bool = True,
            connect_timeout: int = 10,
            connect_retries: int = 4,
            connect_retry_delay: int = 1,
            request_retries: int = 4,
            flood_sleep_threshold: int = 60,
            # Update handling.
            catch_up: bool = False,
            receive_updates: bool = True,
            max_queued_updates: int = 100,
    ):
        telegrambaseclient.init(**locals())

    @property
    def flood_sleep_threshold(self):
        return telegrambaseclient.get_flood_sleep_threshold(**locals())

    @flood_sleep_threshold.setter
    def flood_sleep_threshold(self, value):
        return telegrambaseclient.set_flood_sleep_threshold(**locals())

    @forward_call(telegrambaseclient.connect)
    async def connect(self: 'TelegramClient') -> None:
        """
        Connects to Telegram.

        .. note::

            Connect means connect and nothing else, and only one low-level
            request is made to notify Telegram about which layer we will be
            using.

            Before Telegram sends you updates, you need to make a high-level
            request, like `client.get_me() <telethon.client.users.UserMethods.get_me>`,
            as described in https://core.telegram.org/api/updates.

        Example
            .. code-block:: python

                try:
                    await client.connect()
                except OSError:
                    print('Failed to connect')
        """

    @property
    def is_connected(self: 'TelegramClient') -> bool:
        """
        Returns `True` if the user has connected.

        This method is **not** asynchronous (don't use ``await`` on it).

        Example
            .. code-block:: python

                # This is a silly example - run_until_disconnected is often better suited
                while client.is_connected:
                    await asyncio.sleep(1)
        """
        return telegrambaseclient.is_connected(self)

    @forward_call(telegrambaseclient.disconnect)
    def disconnect(self: 'TelegramClient'):
        """
        Disconnects from Telegram.

        If the event loop is already running, this method returns a
        coroutine that you should await on your own code; otherwise
        the loop is ran until said coroutine completes.

        Example
            .. code-block:: python

                # You don't need to use this if you used "with client"
                await client.disconnect()
        """

    @forward_call(telegrambaseclient.set_proxy)
    def set_proxy(self: 'TelegramClient', proxy: typing.Union[tuple, dict]):
        """
        Changes the proxy which will be used on next (re)connection.

        Method has no immediate effects if the client is currently connected.

        The new proxy will take it's effect on the next reconnection attempt:
            - on a call `await client.connect()` (after complete disconnect)
            - on auto-reconnect attempt (e.g, after previous connection was lost)
        """

    # endregion Base

    # region Updates

    @forward_call(updates.set_receive_updates)
    async def set_receive_updates(self: 'TelegramClient', receive_updates):
        """
        Change the value of `receive_updates`.

        This is an `async` method, because in order for Telegram to start
        sending updates again, a request must be made.
        """

    @forward_call(updates.run_until_disconnected)
    def run_until_disconnected(self: 'TelegramClient'):
        """
        Wait until the library is disconnected.

        It also notifies Telegram that we want to receive updates
        as described in https://core.telegram.org/api/updates.

        Event handlers will continue to run while the method awaits for a
        disconnection to occur. Essentially, this method "blocks" until a
        disconnection occurs, and keeps your code running if you have nothing
        else to do.

        Manual disconnections can be made by calling `disconnect()
        <telethon.client.telegrambaseclient.TelegramBaseClient.disconnect>`
        or exiting the context-manager using the client (for example, a
        ``KeyboardInterrupt`` by pressing ``Ctrl+C`` on the console window
        would propagate the error, exit the ``with`` block and disconnect).

        If a disconnection error occurs (i.e. the library fails to reconnect
        automatically), said error will be raised through here, so you have a
        chance to ``except`` it on your own code.

        Example
            .. code-block:: python

                # Blocks the current task here until a disconnection occurs.
                #
                # You will still receive updates, since this prevents the
                # script from exiting.
                await client.run_until_disconnected()
        """

    @forward_call(updates.on)
    def on(self: 'TelegramClient', *events, priority=0, **filters):
        """
        Decorator used to `add_event_handler` more conveniently.

        This decorator should be above other decorators which modify the function.

        Arguments
            event (`type` | `tuple`):
                The event type(s) you wish to receive, for instance ``events.NewMessage``.
                This may also be raw update types.
                The same handler is registered multiple times, one per type.

            priority (`int`):
                The event priority. Events with higher priority are dispatched first.
                The order between events with the same priority is arbitrary.

            filters (any):
                Filters passed to `make_filter`.

        Example
            .. code-block:: python

                from telethon import TelegramClient, events
                client = TelegramClient(...)

                # Here we use client.on
                @client.on(events.NewMessage, priority=100)
                async def handler(event):
                    ...

                # Both new incoming messages and incoming edits
                @client.on(events.NewMessage, events.MessageEdited, incoming=True)
                async def handler(event):
                    ...
        """

    @forward_call(updates.add_event_handler)
    def add_event_handler(
            self: 'TelegramClient',
            callback: updates.Callback = None,
            event: EventBuilder = None,
            priority=0,
            **filters
    ):
        """
        Registers a new event handler callback.

        The callback will be called when the specified event occurs.

        Arguments
            callback (`callable`):
                The callable function accepting one parameter to be used.

                If `None`, the method can be used as a decorator. Note that the handler function
                will be replaced with the `EventHandler` instance in this case, but it will still
                be callable.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used,
                for instance ``events.NewMessage``.

                If left unspecified, it will be inferred from the type hint
                used in the handler, or be `telethon.events.raw.Raw` (the
                :tl:`Update` objects with no further processing) if there is
                none. Note that the type hint must be the desired type. It
                cannot be a string, an union, or anything more complex.

            priority (`int`):
                The event priority. Events with higher priority are dispatched first.
                The order between events with the same priority is arbitrary.

            filters (any):
                Filters passed to `make_filter`.

        Returns
            An `EventHandler` instance, which can be used

        Example
            .. code-block:: python

                from telethon import TelegramClient, events
                client = TelegramClient(...)

                # Adding a handler, the "boring" way
                async def handler(event):
                    ...

                client.add_event_handler(handler, events.NewMessage, priority=50)

                # Automatic type
                async def handler(event: events.MessageEdited)
                    ...

                client.add_event_handler(handler, outgoing=False)

                # Streamlined adding
                @client.add_event_handler
                async def handler(event: events.MessageDeleted):
                    ...
        """

    @forward_call(updates.remove_event_handler)
    def remove_event_handler(
            self: 'TelegramClient',
            callback: updates.Callback = None,
            event: EventBuilder = None,
            *,
            priority=None,
    ) -> int:
        """
        Inverse operation of `add_event_handler()`.

        If no event is given, all events for this callback are removed.
        Returns a list in arbitrary order with all removed `EventHandler` instances.

        Arguments
            callback (`callable`):
                The callable function accepting one parameter to be used.
                If passed an `EventHandler` instance, both `event` and `priority` are ignored.

            event (`_EventBuilder` | `type`, optional):
                The event builder class or instance to be used when searching.

            priority (`int`):
                The event priority to be used when searching.

        Example
            .. code-block:: python

                @client.on(events.Raw)
                @client.on(events.NewMessage)
                async def handler(event):
                    ...

                # Removes only the "Raw" handling
                # "handler" will still receive "events.NewMessage"
                client.remove_event_handler(handler, events.Raw)

                # "handler" will stop receiving anything
                client.remove_event_handler(handler)

                # Remove all handlers with priority 50
                client.remove_event_handler(priority=50)

                # Remove all deleted-message handlers
                client.remove_event_handler(event=events.MessageDeleted)
        """

    @forward_call(updates.list_event_handlers)
    def list_event_handlers(self: 'TelegramClient')\
            -> 'typing.Sequence[typing.Tuple[Callback, EventBuilder]]':
        """
        Lists all registered event handlers.

        Returns
            A list of all registered `EventHandler` in arbitrary order.

        Example
            .. code-block:: python

                @client.on(events.NewMessage(pattern='hello'))
                async def on_greeting(event):
                    '''Greets someone'''
                    await event.reply('Hi')

                for handler in client.list_event_handlers():
                    print(id(handler.callback), handler.event)
        """

    @forward_call(updates.catch_up)
    async def catch_up(self: 'TelegramClient'):
        """
        Forces the client to "catch-up" on missed updates.

        The method does not wait for all updates to be received.

        Example
            .. code-block:: python

                await client.catch_up()
        """

    # endregion Updates

    # region Uploads

    @forward_call(uploads.send_file)
    async def send_file(
            self: 'TelegramClient',
            dialog: 'hints.DialogLike',
            file: 'typing.Union[hints.FileLike, typing.Sequence[hints.FileLike]]',
            *,
            caption: typing.Union[str, typing.Sequence[str]] = None,
            force_document: bool = False,
            file_size: int = None,
            clear_draft: bool = False,
            progress_callback: 'hints.ProgressCallback' = None,
            reply_to: 'hints.MessageIDLike' = None,
            attributes: 'typing.Sequence[_tl.TypeDocumentAttribute]' = None,
            thumb: 'hints.FileLike' = None,
            allow_cache: bool = True,
            parse_mode: str = (),
            formatting_entities: typing.Optional[typing.List[_tl.TypeMessageEntity]] = None,
            voice_note: bool = False,
            video_note: bool = False,
            buttons: 'hints.MarkupLike' = None,
            silent: bool = None,
            background: bool = None,
            supports_streaming: bool = False,
            schedule: 'hints.DateLike' = None,
            comment_to: 'typing.Union[int, _tl.Message]' = None,
            ttl: int = None,
            **kwargs) -> '_tl.Message':
        """
        Sends message with the given file to the specified entity.

        .. note::

            If the ``hachoir3`` package (``hachoir`` module) is installed,
            it will be used to determine metadata from audio and video files.

            If the ``pillow`` package is installed and you are sending a photo,
            it will be resized to fit within the maximum dimensions allowed
            by Telegram to avoid ``errors.PhotoInvalidDimensionsError``. This
            cannot be done if you are sending :tl:`InputFile`, however.

        Arguments
            dialog (`entity`):
                Who will receive the file.

            file (`str` | `bytes` | `file` | `media`):
                The file to send, which can be one of:

                * A local file path to an in-disk file. The file name
                  will be the path's base name.

                * A `bytes` byte array with the file's data to send
                  (for example, by using ``text.encode('utf-8')``).
                  A default file name will be used.

                * A bytes `io.IOBase` stream over the file to send
                  (for example, by using ``open(file, 'rb')``).
                  Its ``.name`` property will be used for the file name,
                  or a default if it doesn't have one.

                * An external URL to a file over the internet. This will
                  send the file as "external" media, and Telegram is the
                  one that will fetch the media and send it.

                * A handle to an existing file (for example, if you sent a
                  message with media before, you can use its ``message.media``
                  as a file here).

                * A :tl:`InputMedia` instance. For example, if you want to
                  send a dice use :tl:`InputMediaDice`, or if you want to
                  send a contact use :tl:`InputMediaContact`.

                To send an album, you should provide a list in this parameter.

                If a list or similar is provided, the files in it will be
                sent as an album in the order in which they appear, sliced
                in chunks of 10 if more than 10 are given.

            caption (`str`, optional):
                Optional caption for the sent media message. When sending an
                album, the caption may be a list of strings, which will be
                assigned to the files pairwise.

            force_document (`bool`, optional):
                If left to `False` and the file is a path that ends with
                the extension of an image file or a video file, it will be
                sent as such. Otherwise always as a document.

            file_size (`int`, optional):
                The size of the file to be uploaded if it needs to be uploaded,
                which will be determined automatically if not specified.

                If the file size can't be determined beforehand, the entire
                file will be read in-memory to find out how large it is.

            clear_draft (`bool`, optional):
                Whether the existing draft should be cleared or not.

            progress_callback (`callable`, optional):
                A callback function accepting two parameters:
                ``(sent bytes, total)``.

            reply_to (`int` | `Message <telethon.tl._custom.message.Message>`):
                Same as `reply_to` from `send_message`.

            attributes (`list`, optional):
                Optional attributes that override the inferred ones, like
                :tl:`DocumentAttributeFilename` and so on.

            thumb (`str` | `bytes` | `file`, optional):
                Optional JPEG thumbnail (for documents). **Telegram will
                ignore this parameter** unless you pass a ``.jpg`` file!

                The file must also be small in dimensions and in disk size.
                Successful thumbnails were files below 20kB and 320x320px.
                Width/height and dimensions/size ratios may be important.
                For Telegram to accept a thumbnail, you must provide the
                dimensions of the underlying media through ``attributes=``
                with :tl:`DocumentAttributesVideo` or by installing the
                optional ``hachoir`` dependency.


            allow_cache (`bool`, optional):
                This parameter currently does nothing, but is kept for
                backward-compatibility (and it may get its use back in
                the future).

            parse_mode (`object`, optional):
                See the `TelegramClient.parse_mode
                <telethon.client.messageparse.MessageParseMethods.parse_mode>`
                property for allowed values. Markdown parsing will be used by
                default.

            formatting_entities (`list`, optional):
                A list of message formatting entities. When provided, the ``parse_mode`` is ignored.

            voice_note (`bool`, optional):
                If `True` the audio will be sent as a voice note.

            video_note (`bool`, optional):
                If `True` the video will be sent as a video note,
                also known as a round video message.

            buttons (`list`, `_custom.Button <telethon.tl._custom.button.Button>`, :tl:`KeyboardButton`):
                The matrix (list of lists), row list or button to be shown
                after sending the message. This parameter will only work if
                you have signed in as a bot. You can also pass your own
                :tl:`ReplyMarkup` here.

            silent (`bool`, optional):
                Whether the message should notify people with sound or not.
                Defaults to `False` (send with a notification sound unless
                the person has the chat muted). Set it to `True` to alter
                this behaviour.

            background (`bool`, optional):
                Whether the message should be send in background.

            supports_streaming (`bool`, optional):
                Whether the sent video supports streaming or not. Note that
                Telegram only recognizes as streamable some formats like MP4,
                and others like AVI or MKV will not work. You should convert
                these to MP4 before sending if you want them to be streamable.
                Unsupported formats will result in ``VideoContentTypeError``.

            schedule (`hints.DateLike`, optional):
                If set, the file won't send immediately, and instead
                it will be scheduled to be automatically sent at a later
                time.

            comment_to (`int` | `Message <telethon.tl._custom.message.Message>`, optional):
                Similar to ``reply_to``, but replies in the linked group of a
                broadcast channel instead (effectively leaving a "comment to"
                the specified message).

                This parameter takes precedence over ``reply_to``. If there is
                no linked chat, `telethon.errors.sgIdInvalidError` is raised.

            ttl (`int`. optional):
                The Time-To-Live of the file (also known as "self-destruct timer"
                or "self-destructing media"). If set, files can only be viewed for
                a short period of time before they disappear from the message
                history automatically.

                The value must be at least 1 second, and at most 60 seconds,
                otherwise Telegram will ignore this parameter.

                Not all types of media can be used with this parameter, such
                as text documents, which will fail with ``TtlMediaInvalidError``.

        Returns
            The `Message <telethon.tl._custom.message.Message>` (or messages)
            containing the sent file, or messages if a list of them was passed.

        Example
            .. code-block:: python

                # Normal files like photos
                await client.send_file(chat, '/my/photos/me.jpg', caption="It's me!")
                # or
                await client.send_message(chat, "It's me!", file='/my/photos/me.jpg')

                # Voice notes or round videos
                await client.send_file(chat, '/my/songs/song.mp3', voice_note=True)
                await client.send_file(chat, '/my/videos/video.mp4', video_note=True)

                # _custom thumbnails
                await client.send_file(chat, '/my/documents/doc.txt', thumb='photo.jpg')

                # Only documents
                await client.send_file(chat, '/my/photos/photo.png', force_document=True)

                # Albums
                await client.send_file(chat, [
                    '/my/photos/holiday1.jpg',
                    '/my/photos/holiday2.jpg',
                    '/my/drawings/portrait.png'
                ])

                # Printing upload progress
                def callback(current, total):
                    print('Uploaded', current, 'out of', total,
                          'bytes: {:.2%}'.format(current / total))

                await client.send_file(chat, file, progress_callback=callback)

                # Dices, including dart and other future emoji
                from telethon import _tl
                await client.send_file(chat, _tl.InputMediaDice(''))
                await client.send_file(chat, _tl.InputMediaDice('🎯'))

                # Contacts
                await client.send_file(chat, _tl.InputMediaContact(
                    phone_number='+34 123 456 789',
                    first_name='Example',
                    last_name='',
                    vcard=''
                ))
        """

    # endregion Uploads

    # region Users

    @forward_call(users.call)
    async def __call__(self: 'TelegramClient', request, ordered=False, flood_sleep_threshold=None):
        """
        Invokes (sends) one or more MTProtoRequests and returns (receives)
        their result.

        Args:
            request (`TLObject` | `list`):
                The request or requests to be invoked.

            ordered (`bool`, optional):
                Whether the requests (if more than one was given) should be
                executed sequentially on the server. They run in arbitrary
                order by default.

            flood_sleep_threshold (`int` | `None`, optional):
                The flood sleep threshold to use for this request. This overrides
                the default value stored in
                `client.flood_sleep_threshold <telethon.client.telegrambaseclient.TelegramBaseClient.flood_sleep_threshold>`

        Returns:
            The result of the request (often a `TLObject`) or a list of
            results if more than one request was given.
        """

    @forward_call(users.get_me)
    async def get_me(self: 'TelegramClient') \
            -> '_tl.User':
        """
        Gets "me", the current :tl:`User` who is logged in.

        If the user has not logged in yet, this method returns `None`.

        Returns
            Your own :tl:`User`.

        Example
            .. code-block:: python

                me = await client.get_me()
                print(me.username)
        """

    @forward_call(users.is_bot)
    async def is_bot(self: 'TelegramClient') -> bool:
        """
        Return `True` if the signed-in user is a bot, `False` otherwise.

        Example
            .. code-block:: python

                if await client.is_bot():
                    print('Beep')
                else:
                    print('Hello')
        """

    @forward_call(users.is_user_authorized)
    async def is_user_authorized(self: 'TelegramClient') -> bool:
        """
        Returns `True` if the user is authorized (logged in).

        Example
            .. code-block:: python

                if not await client.is_user_authorized():
                    await client.send_code_request(phone)
                    code = input('enter code: ')
                    await client.sign_in(phone, code)
        """

    @forward_call(users.get_profile)
    async def get_profile(
            self: 'TelegramClient',
            profile: 'hints.DialogsLike') -> 'hints.Entity':
        """
        Turns the given profile reference into a `User <telethon.types._custom.user.User>`
        or `Chat <telethon.types._custom.chat.Chat>` instance.

        Arguments
            profile (`str` | `int` | :tl:`Peer` | :tl:`InputPeer`):
                If a username is given, **the username will be resolved** making
                an API call every time. Resolving usernames is an expensive
                operation and will start hitting flood waits around 50 usernames
                in a short period of time.

                Using phone numbers with strings will fetch your contact list first.

                Using integer IDs will only work if the ID is in the session cache.

                ``'me'`` is a special-case to the logged-in account (yourself).

                Unsupported types will raise ``TypeError``.

                If the user or chat can't be found, ``ValueError`` will be raised.

        Returns
            `User <telethon.types._custom.user.User>` or `Chat <telethon.types._custom.chat.Chat>`,
            depending on the profile requested.

        Example
            .. code-block:: python

                from telethon import utils

                me = await client.get_profile('me')
                print(utils.get_display_name(me))

                chat = await client.get_profile('username')
                async for message in client.get_messages(chat):
                    ...

                # Note that you could have used the username directly, but it's
                # good to use get_profile if you will reuse it a lot.
                async for message in client.get_messages('username'):
                    ...

                # Note that for this to work the phone number must be in your contacts
                some_id = (await client.get_profile('+34123456789')).id
        """

    # endregion Users

    # region Private

    @forward_call(users._call)
    async def _call(self: 'TelegramClient', sender, request, ordered=False, flood_sleep_threshold=None):
        pass

    @forward_call(updates._update_loop)
    async def _update_loop(self: 'TelegramClient'):
        pass

    @forward_call(messageparse._parse_message_text)
    async def _parse_message_text(self: 'TelegramClient', message, parse_mode):
        pass

    @forward_call(messageparse._get_response_message)
    def _get_response_message(self: 'TelegramClient', request, result, input_chat):
        pass

    @forward_call(messages._get_comment_data)
    async def _get_comment_data(
            self: 'TelegramClient',
            entity: 'hints.DialogLike',
            message: 'typing.Union[int, _tl.Message]'
    ):
        pass

    @forward_call(telegrambaseclient._switch_dc)
    async def _switch_dc(self: 'TelegramClient', new_dc):
        pass

    @forward_call(telegrambaseclient._borrow_exported_sender)
    async def _borrow_exported_sender(self: 'TelegramClient', dc_id):
        pass

    @forward_call(telegrambaseclient._return_exported_sender)
    async def _return_exported_sender(self: 'TelegramClient', sender):
        pass

    @forward_call(telegrambaseclient._clean_exported_senders)
    async def _clean_exported_senders(self: 'TelegramClient'):
        pass

    @forward_call(auth._update_session_state)
    async def _update_session_state(self, user, *, save=True):
        pass

    @forward_call(auth._replace_session_state)
    async def _replace_session_state(self, *, save=True, **changes):
        pass

    @forward_call(uploads.upload_file)
    async def _upload_file(
            self: 'TelegramClient',
            file: 'hints.FileLike',
            *,
            part_size_kb: float = None,
            file_size: int = None,
            file_name: str = None,
            use_cache: type = None,
            key: bytes = None,
            iv: bytes = None,
            progress_callback: 'hints.ProgressCallback' = None) -> '_tl.TypeInputFile':
        pass

    @forward_call(users._get_input_peer)
    async def _get_input_peer(self, *, save=True, **changes):
        pass

    @forward_call(users._get_peer_id)
    async def _get_peer_id(self, *, save=True, **changes):
        pass

    # endregion Private
