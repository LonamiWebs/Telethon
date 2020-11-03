import getpass
import inspect
import os
import sys
import typing
import warnings

from .. import utils, helpers, errors, password as pwd_mod
from ..tl import types, functions, custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class AuthMethods:

    # region Public methods

    def start(
            self: 'TelegramClient',
            phone: typing.Callable[[], str] = lambda: input('Please enter your phone (or bot token): '),
            password: typing.Callable[[], str] = lambda: getpass.getpass('Please enter your password: '),
            *,
            bot_token: str = None,
            force_sms: bool = False,
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

        If the event loop is already running, this method returns a
        coroutine that you should await on your own code; otherwise
        the loop is ran until said coroutine completes.

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

            force_sms (`bool`, optional):
                Whether to force sending the code request as SMS.
                This only makes sense when signing in with a `phone`.

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

                # Starting using a context manager (this calls start()):
                with client:
                    pass
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

        coro = self._start(
            phone=phone,
            password=password,
            bot_token=bot_token,
            force_sms=force_sms,
            code_callback=code_callback,
            first_name=first_name,
            last_name=last_name,
            max_attempts=max_attempts
        )
        return (
            coro if self.loop.is_running()
            else self.loop.run_until_complete(coro)
        )

    async def _start(
            self: 'TelegramClient', phone, password, bot_token, force_sms,
            code_callback, first_name, last_name, max_attempts):
        if not self.is_connected():
            await self.connect()

        # Rather than using `is_user_authorized`, use `get_me`. While this is
        # more expensive and needs to retrieve more data from the server, it
        # enables the library to warn users trying to login to a different
        # account. See #1172.
        me = await self.get_me()
        if me is not None:
            # The warnings here are on a best-effort and may fail.
            if bot_token:
                # bot_token's first part has the bot ID, but it may be invalid
                # so don't try to parse as int (instead cast our ID to string).
                if bot_token[:bot_token.find(':')] != str(me.id):
                    warnings.warn(
                        'the session already had an authorized user so it did '
                        'not login to the bot account using the provided '
                        'bot_token (it may not be using the user you expect)'
                    )
            elif phone and not callable(phone) and utils.parse_phone(phone) != me.phone:
                warnings.warn(
                    'the session already had an authorized user so it did '
                    'not login to the user account using the provided '
                    'phone (it may not be using the user you expect)'
                )

            return self

        if not bot_token:
            # Turn the callable into a valid phone number (or bot token)
            while callable(phone):
                value = phone()
                if inspect.isawaitable(value):
                    value = await value

                if ':' in value:
                    # Bot tokens have 'user_id:access_hash' format
                    bot_token = value
                    break

                phone = utils.parse_phone(value) or phone

        if bot_token:
            await self.sign_in(bot_token=bot_token)
            return self

        me = None
        attempts = 0
        two_step_detected = False

        await self.send_code_request(phone, force_sms=force_sms)
        sign_up = False  # assume login
        while attempts < max_attempts:
            try:
                value = code_callback()
                if inspect.isawaitable(value):
                    value = await value

                # Since sign-in with no code works (it sends the code)
                # we must double-check that here. Else we'll assume we
                # logged in, and it will return None as the User.
                if not value:
                    raise errors.PhoneCodeEmptyError(request=None)

                if sign_up:
                    me = await self.sign_up(value, first_name, last_name)
                else:
                    # Raises SessionPasswordNeededError if 2FA enabled
                    me = await self.sign_in(phone, code=value)
                break
            except errors.SessionPasswordNeededError:
                two_step_detected = True
                break
            except errors.PhoneNumberOccupiedError:
                sign_up = False
            except errors.PhoneNumberUnoccupiedError:
                sign_up = True
            except (errors.PhoneCodeEmptyError,
                    errors.PhoneCodeExpiredError,
                    errors.PhoneCodeHashEmptyError,
                    errors.PhoneCodeInvalidError):
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

            if callable(password):
                for _ in range(max_attempts):
                    try:
                        value = password()
                        if inspect.isawaitable(value):
                            value = await value

                        me = await self.sign_in(phone=phone, password=value)
                        break
                    except errors.PasswordHashInvalidError:
                        print('Invalid password. Please try again',
                              file=sys.stderr)
                else:
                    raise errors.PasswordHashInvalidError(request=None)
            else:
                me = await self.sign_in(phone=phone, password=password)

        # We won't reach here if any step failed (exit by exception)
        signed, name = 'Signed in successfully as', utils.get_display_name(me)
        try:
            print(signed, name)
        except UnicodeEncodeError:
            # Some terminals don't support certain characters
            print(signed, name.encode('utf-8', errors='ignore')
                              .decode('ascii', errors='ignore'))

        return self

    def _parse_phone_and_hash(self, phone, phone_hash):
        """
        Helper method to both parse and validate phone and its hash.
        """
        phone = utils.parse_phone(phone) or self._phone
        if not phone:
            raise ValueError(
                'Please make sure to call send_code_request first.'
            )

        phone_hash = phone_hash or self._phone_code_hash.get(phone, None)
        if not phone_hash:
            raise ValueError('You also need to provide a phone_code_hash.')

        return phone, phone_hash

    async def sign_in(
            self: 'TelegramClient',
            phone: str = None,
            code: typing.Union[str, int] = None,
            *,
            password: str = None,
            bot_token: str = None,
            phone_code_hash: str = None) -> 'typing.Union[types.User, types.auth.SentCode]':
        """
        Logs in to Telegram to an existing user or bot account.

        You should only use this if you are not authorized yet.

        This method will send the code if it's not provided.

        .. note::

            In most cases, you should simply use `start()` and not this method.

        Arguments
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
                ``SessionPasswordNeededError``.

            bot_token (`str`):
                Used to sign in as a bot. Not all requests will be available.
                This should be the hash the `@BotFather <https://t.me/BotFather>`_
                gave you.

            phone_code_hash (`str`, optional):
                The hash returned by `send_code_request`. This can be left as
                `None` to use the last hash known for the phone to be used.

        Returns
            The signed in user, or the information about
            :meth:`send_code_request`.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                await client.sign_in(phone)  # send code

                code = input('enter code: ')
                await client.sign_in(phone, code)
        """
        me = await self.get_me()
        if me:
            return me

        if phone and not code and not password:
            return await self.send_code_request(phone)
        elif code:
            phone, phone_code_hash = \
                self._parse_phone_and_hash(phone, phone_code_hash)

            # May raise PhoneCodeEmptyError, PhoneCodeExpiredError,
            # PhoneCodeHashEmptyError or PhoneCodeInvalidError.
            request = functions.auth.SignInRequest(
                phone, phone_code_hash, str(code)
            )
        elif password:
            pwd = await self(functions.account.GetPasswordRequest())
            request = functions.auth.CheckPasswordRequest(
                pwd_mod.compute_check(pwd, password)
            )
        elif bot_token:
            request = functions.auth.ImportBotAuthorizationRequest(
                flags=0, bot_auth_token=bot_token,
                api_id=self.api_id, api_hash=self.api_hash
            )
        else:
            raise ValueError(
                'You must provide a phone and a code the first time, '
                'and a password only if an RPCError was raised before.'
            )

        result = await self(request)
        if isinstance(result, types.auth.AuthorizationSignUpRequired):
            # Emulate pre-layer 104 behaviour
            self._tos = result.terms_of_service
            raise errors.PhoneNumberUnoccupiedError(request=request)

        return self._on_login(result.user)

    async def sign_up(
            self: 'TelegramClient',
            code: typing.Union[str, int],
            first_name: str,
            last_name: str = '',
            *,
            phone: str = None,
            phone_code_hash: str = None) -> 'types.User':
        """
        Signs up to Telegram as a new user account.

        Use this if you don't have an account yet.

        You must call `send_code_request` first.

        **By using this method you're agreeing to Telegram's
        Terms of Service. This is required and your account
        will be banned otherwise.** See https://telegram.org/tos
        and https://core.telegram.org/api/terms.

        Arguments
            code (`str` | `int`):
                The code sent by Telegram

            first_name (`str`):
                The first name to be used by the new account.

            last_name (`str`, optional)
                Optional last name.

            phone (`str` | `int`, optional):
                The phone to sign up. This will be the last phone used by
                default (you normally don't need to set this).

            phone_code_hash (`str`, optional):
                The hash returned by `send_code_request`. This can be left as
                `None` to use the last hash known for the phone to be used.

        Returns
            The new created :tl:`User`.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                await client.send_code_request(phone)

                code = input('enter code: ')
                await client.sign_up(code, first_name='Anna', last_name='Banana')
        """
        me = await self.get_me()
        if me:
            return me

        # To prevent abuse, one has to try to sign in before signing up. This
        # is the current way in which Telegram validates the code to sign up.
        #
        # `sign_in` will set `_tos`, so if it's set we don't need to call it
        # because the user already tried to sign in.
        #
        # We're emulating pre-layer 104 behaviour so except the right error:
        if not self._tos:
            try:
                return await self.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
            except errors.PhoneNumberUnoccupiedError:
                pass  # code is correct and was used, now need to sign in

        if self._tos and self._tos.text:
            if self.parse_mode:
                t = self.parse_mode.unparse(self._tos.text, self._tos.entities)
            else:
                t = self._tos.text
            sys.stderr.write("{}\n".format(t))
            sys.stderr.flush()

        phone, phone_code_hash = \
            self._parse_phone_and_hash(phone, phone_code_hash)

        result = await self(functions.auth.SignUpRequest(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
            first_name=first_name,
            last_name=last_name
        ))

        if self._tos:
            await self(
                functions.help.AcceptTermsOfServiceRequest(self._tos.id))

        return self._on_login(result.user)

    def _on_login(self, user):
        """
        Callback called whenever the login or sign up process completes.

        Returns the input user parameter.
        """
        self._bot = bool(user.bot)
        self._self_input_peer = utils.get_input_peer(user, allow_self=False)
        self._authorized = True

        return user

    async def send_code_request(
            self: 'TelegramClient',
            phone: str,
            *,
            force_sms: bool = False) -> 'types.auth.SentCode':
        """
        Sends the Telegram code needed to login to the given phone number.

        Arguments
            phone (`str` | `int`):
                The phone to which the code will be sent.

            force_sms (`bool`, optional):
                Whether to force sending as SMS.

        Returns
            An instance of :tl:`SentCode`.

        Example
            .. code-block:: python

                phone = '+34 123 123 123'
                sent = await client.send_code_request(phone)
                print(sent)
        """
        result = None
        phone = utils.parse_phone(phone) or self._phone
        phone_hash = self._phone_code_hash.get(phone)

        if not phone_hash:
            try:
                result = await self(functions.auth.SendCodeRequest(
                    phone, self.api_id, self.api_hash, types.CodeSettings()))
            except errors.AuthRestartError:
                return await self.send_code_request(phone, force_sms=force_sms)

            # If we already sent a SMS, do not resend the code (hash may be empty)
            if isinstance(result.type, types.auth.SentCodeTypeSms):
                force_sms = False

            # phone_code_hash may be empty, if it is, do not save it (#1283)
            if result.phone_code_hash:
                self._phone_code_hash[phone] = phone_hash = result.phone_code_hash
        else:
            force_sms = True

        self._phone = phone

        if force_sms:
            result = await self(
                functions.auth.ResendCodeRequest(phone, phone_hash))

            self._phone_code_hash[phone] = result.phone_code_hash

        return result

    async def qr_login(self: 'TelegramClient', ignored_ids: typing.List[int] = None) -> custom.QRLogin:
        """
        Initiates the QR login procedure.

        Note that you must be connected before invoking this, as with any
        other request.

        It is up to the caller to decide how to present the code to the user,
        whether it's the URL, using the token bytes directly, or generating
        a QR code and displaying it by other means.

        See the documentation for `QRLogin` to see how to proceed after this.

        Arguments
            ignored_ids (List[`int`]):
                List of already logged-in user IDs, to prevent logging in
                twice with the same user.

        Returns
            An instance of `QRLogin`.

        Example
            .. code-block:: python

                def display_url_as_qr(url):
                    pass  # do whatever to show url as a qr to the user

                qr_login = await client.qr_login()
                display_url_as_qr(qr_login.url)

                # Important! You need to wait for the login to complete!
                await qr_login.wait()
        """
        qr_login = custom.QRLogin(self, ignored_ids or [])
        await qr_login.recreate()
        return qr_login

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
        try:
            await self(functions.auth.LogOutRequest())
        except errors.RPCError:
            return False

        self._bot = None
        self._self_input_peer = None
        self._authorized = False
        self._state_cache.reset()

        await self.disconnect()
        self.session.delete()
        return True

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
        if new_password is None and current_password is None:
            return False

        if email and not callable(email_code_callback):
            raise ValueError('email present without email_code_callback')

        pwd = await self(functions.account.GetPasswordRequest())
        pwd.new_algo.salt1 += os.urandom(32)
        assert isinstance(pwd, types.account.Password)
        if not pwd.has_password and current_password:
            current_password = None

        if current_password:
            password = pwd_mod.compute_check(pwd, current_password)
        else:
            password = types.InputCheckPasswordEmpty()

        if new_password:
            new_password_hash = pwd_mod.compute_digest(
                pwd.new_algo, new_password)
        else:
            new_password_hash = b''

        try:
            await self(functions.account.UpdatePasswordSettingsRequest(
                password=password,
                new_settings=types.account.PasswordInputSettings(
                    new_algo=pwd.new_algo,
                    new_password_hash=new_password_hash,
                    hint=hint,
                    email=email,
                    new_secure_settings=None
                )
            ))
        except errors.EmailUnconfirmedError as e:
            code = email_code_callback(e.code_length)
            if inspect.isawaitable(code):
                code = await code

            code = str(code)
            await self(functions.account.ConfirmPasswordEmailRequest(code))

        return True

    # endregion

    # region with blocks

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *args):
        await self.disconnect()

    __enter__ = helpers._sync_enter
    __exit__ = helpers._sync_exit

    # endregion
