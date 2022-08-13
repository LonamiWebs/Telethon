import asyncio
import getpass
import inspect
import os
import sys
import typing
import warnings
import functools
import time
import dataclasses

from .._misc import utils, helpers, password as pwd_mod
from .. import errors, _tl
from ..types import _custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class StartingClient:
    def __init__(self, client, start_fn):
        self.client = client
        self.start_fn = start_fn

    async def __aenter__(self):
        await self.start_fn()
        return self.client

    async def __aexit__(self, *args):
        await self.client.__aexit__(*args)

    def __await__(self):
        return self.__aenter__().__await__()


def start(
        self: 'TelegramClient',
        phone: typing.Callable[[], str] = lambda: input('Please enter your phone (or bot token): '),
        password: typing.Callable[[], str] = lambda: getpass.getpass('Please enter your password: '),
        *,
        bot_token: str = None,
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

    return StartingClient(self, functools.partial(_start,
        self=self,
        phone=phone,
        password=password,
        bot_token=bot_token,
        code_callback=code_callback,
        first_name=first_name,
        last_name=last_name,
        max_attempts=max_attempts
    ))

async def _start(
        self: 'TelegramClient', phone, password, bot_token,
        code_callback, first_name, last_name, max_attempts):
    if not self.is_connected:
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

    await self.send_code_request(phone)
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


async def sign_in(
        self: 'TelegramClient',
        *,
        code: typing.Union[str, int] = None,
        password: str = None,
        bot_token: str = None,) -> 'typing.Union[_tl.User, _tl.auth.SentCode]':
    if code and bot_token:
        raise ValueError('Can only provide one of code or bot_token, not both')

    if not code and not bot_token and not password:
        raise ValueError('You must provide code, password, or bot_token.')

    if code:
        if not self._phone_code_hash:
            raise ValueError('Must call client.send_code_request before sign in')

        # May raise PhoneCodeEmptyError, PhoneCodeExpiredError,
        # PhoneCodeHashEmptyError or PhoneCodeInvalidError.
        try:
            result = await self(_tl.fn.auth.SignIn(*self._phone_code_hash, str(code)))
            password = None  # user provided a password but it was not needed
        except errors.SessionPasswordNeededError:
            if not password:
                raise
    elif bot_token:
        result = await self(_tl.fn.auth.ImportBotAuthorization(
            flags=0, bot_auth_token=bot_token,
            api_id=self._api_id, api_hash=self._api_hash
        ))

    if password:
        pwd = await self(_tl.fn.account.GetPassword())
        result = await self(_tl.fn.auth.CheckPassword(
            pwd_mod.compute_check(pwd, password)
        ))

    if isinstance(result, _tl.auth.AuthorizationSignUpRequired):
        # The method must return the User but we don't have it, so raise instead (matches pre-layer 104 behaviour)
        self._tos = (result.terms_of_service, None)
        raise errors.SignUpRequired()

    return await _update_session_state(self, result.user)


async def sign_up(
        self: 'TelegramClient',
        first_name: str,
        last_name: str = '',
        *,
        code: typing.Union[str, int]) -> '_tl.User':
    if not self._phone_code_hash:
        # This check is also present in sign_in but we do it here to customize the error message
        raise ValueError('Must call client.send_code_request before sign up')

    # To prevent abuse, one has to try to sign in before signing up. This
    # is the current way in which Telegram validates the code to sign up.
    #
    # `sign_in` will set `_tos`, so if it's set we don't need to call it
    # because the user already tried to sign in.
    #
    # We're emulating pre-layer 104 behaviour so except the right error:
    try:
        return await self.sign_in(code=code)
    except errors.SignUpRequired:
        pass  # code is correct and was used, now need to sign in

    result = await self(_tl.fn.auth.SignUp(
        phone_number=phone,
        phone_code_hash=phone_code_hash,
        first_name=first_name,
        last_name=last_name
    ))

    return await _update_session_state(self, result.user)


async def get_tos(self):
    first_time = self._tos is None
    no_tos = self._tos and self._tos[0] is None
    tos_expired = self._tos and self._tos[1] is not None and asyncio.get_running_loop().time() >= self._tos[1]

    if first_time or no_tos or tos_expired:
        result = await self(_tl.fn.help.GetTermsOfServiceUpdate())
        tos = getattr(result, 'terms_of_service', None)
        self._tos = (tos, asyncio.get_running_loop().time() + result.expires.timestamp() - time.time())

    # not stored in the client to prevent a cycle
    return _custom.TermsOfService._new(self, *self._tos)


async def _update_session_state(self, user, save=True):
    """
    Callback called whenever the login or sign up process completes.
    Returns the input user parameter.
    """
    state = await self(_tl.fn.updates.GetState())
    await _replace_session_state(
        self,
        save=save,
        user_id=user.id,
        bot=user.bot,
        pts=state.pts,
        qts=state.qts,
        date=int(state.date.timestamp()),
        seq=state.seq,
    )

    self._phone_code_hash = None
    return _custom.User._new(self, user)


async def _replace_session_state(self, *, save=True, **changes):
    new = dataclasses.replace(self._session_state, **changes)
    await self._session.set_state(new)
    self._session_state = new

    if save:
        await self._session.save()


async def send_code_request(
        self: 'TelegramClient',
        phone: str) -> 'SentCode':
    phone = utils.parse_phone(phone)

    if self._phone_code_hash and phone == self._phone_code_hash[0]:
        result = await self(_tl.fn.auth.ResendCode(*self._phone_code_hash))
    else:
        try:
            result = await self(_tl.fn.auth.SendCode(
                phone, self._api_id, self._api_hash, _tl.CodeSettings()))
        except errors.AuthRestartError:
            return await self.send_code_request(phone)

        # phone_code_hash may be empty, if it is, do not save it (#1283)
        if not result.phone_code_hash:
            # The hash is required to login, so this pretty much means send code failed
            raise ValueError('Failed to send code')

    self._phone_code_hash = (phone, result.phone_code_hash)
    return _custom.SentCode._new(result)


def qr_login(self: 'TelegramClient', ignored_ids: typing.List[int] = None) -> _custom.QrLogin:
    return _custom.QrLoginManager(self, ignored_ids)


async def log_out(self: 'TelegramClient') -> bool:
    try:
        await self(_tl.fn.auth.LogOut())
    except errors.RpcError:
        return False

    await self.disconnect()
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
