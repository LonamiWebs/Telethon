import getpass
import inspect
import os
import sys
import typing
import warnings

from .. import utils, helpers, errors, password as pwd_mod, _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


async def start(
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

    return await self._start(
        phone=phone,
        password=password,
        bot_token=bot_token,
        force_sms=force_sms,
        code_callback=code_callback,
        first_name=first_name,
        last_name=last_name,
        max_attempts=max_attempts
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
        phone_code_hash: str = None) -> 'typing.Union[_tl.User, _tl.auth.SentCode]':
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
        request = _tl.fn.auth.SignIn(
            phone, phone_code_hash, str(code)
        )
    elif password:
        pwd = await self(_tl.fn.account.GetPassword())
        request = _tl.fn.auth.CheckPassword(
            pwd_mod.compute_check(pwd, password)
        )
    elif bot_token:
        request = _tl.fn.auth.ImportBotAuthorization(
            flags=0, bot_auth_token=bot_token,
            api_id=self.api_id, api_hash=self.api_hash
        )
    else:
        raise ValueError(
            'You must provide a phone and a code the first time, '
            'and a password only if an RPCError was raised before.'
        )

    result = await self(request)
    if isinstance(result, _tl.auth.AuthorizationSignUpRequired):
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
        phone_code_hash: str = None) -> '_tl.User':
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

    result = await self(_tl.fn.auth.SignUp(
        phone_number=phone,
        phone_code_hash=phone_code_hash,
        first_name=first_name,
        last_name=last_name
    ))

    if self._tos:
        await self(
            _tl.fn.help.AcceptTermsOfService(self._tos.id))

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
        force_sms: bool = False) -> '_tl.auth.SentCode':
    result = None
    phone = utils.parse_phone(phone) or self._phone
    phone_hash = self._phone_code_hash.get(phone)

    if not phone_hash:
        try:
            result = await self(_tl.fn.auth.SendCode(
                phone, self.api_id, self.api_hash, _tl.CodeSettings()))
        except errors.AuthRestartError:
            return await self.send_code_request(phone, force_sms=force_sms)

        # If we already sent a SMS, do not resend the code (hash may be empty)
        if isinstance(result.type, _tl.auth.SentCodeTypeSms):
            force_sms = False

        # phone_code_hash may be empty, if it is, do not save it (#1283)
        if result.phone_code_hash:
            self._phone_code_hash[phone] = phone_hash = result.phone_code_hash
    else:
        force_sms = True

    self._phone = phone

    if force_sms:
        result = await self(
            _tl.fn.auth.ResendCode(phone, phone_hash))

        self._phone_code_hash[phone] = result.phone_code_hash

    return result

async def qr_login(self: 'TelegramClient', ignored_ids: typing.List[int] = None) -> custom.QRLogin:
    qr_login = custom.QRLogin(self, ignored_ids or [])
    await qr_login.recreate()
    return qr_login

async def log_out(self: 'TelegramClient') -> bool:
    try:
        await self(_tl.fn.auth.LogOut())
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
    if new_password is None and current_password is None:
        return False

    if email and not callable(email_code_callback):
        raise ValueError('email present without email_code_callback')

    pwd = await self(_tl.fn.account.GetPassword())
    pwd.new_algo.salt1 += os.urandom(32)
    assert isinstance(pwd, _tl.account.Password)
    if not pwd.has_password and current_password:
        current_password = None

    if current_password:
        password = pwd_mod.compute_check(pwd, current_password)
    else:
        password = _tl.InputCheckPasswordEmpty()

    if new_password:
        new_password_hash = pwd_mod.compute_digest(
            pwd.new_algo, new_password)
    else:
        new_password_hash = b''

    try:
        await self(_tl.fn.account.UpdatePasswordSettings(
            password=password,
            new_settings=_tl.account.PasswordInputSettings(
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
        await self(_tl.fn.account.ConfirmPasswordEmail(code))

    return True
