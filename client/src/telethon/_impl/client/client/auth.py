from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from ...mtproto.mtp.types import RpcError
from ...session.message_box.defs import Session
from ...session.message_box.defs import User as SessionUser
from ...tl import abcs, functions, types
from ..types.chat.user import User
from ..types.login_token import LoginToken
from ..types.password_token import PasswordToken
from .net import connect_sender

if TYPE_CHECKING:
    from .client import Client


async def is_authorized(self: Client) -> bool:
    try:
        await self(functions.updates.get_state())
        return True
    except RpcError as e:
        if e.code == 401:
            return False
        raise


async def complete_login(self: Client, auth: abcs.auth.Authorization) -> User:
    assert isinstance(auth, types.auth.Authorization)
    assert isinstance(auth.user, types.User)
    user = User._from_raw(auth.user)
    self._config.session.user = SessionUser(
        id=user.id,
        dc=self._dc_id,
        bot=user.bot,
    )

    packed = user.pack()
    assert packed is not None
    self._chat_hashes.set_self_user(packed)

    try:
        state = await self(functions.updates.get_state())
        self._message_box.set_state(state)
    except Exception:
        pass

    return user


async def handle_migrate(self: Client, dc_id: Optional[int]) -> None:
    assert dc_id is not None
    sender = await connect_sender(dc_id, self._config)
    async with self._sender_lock:
        self._sender = sender
    self._dc_id = dc_id


async def bot_sign_in(self: Client, token: str) -> User:
    request = functions.auth.import_bot_authorization(
        flags=0,
        api_id=self._config.api_id,
        api_hash=self._config.api_hash,
        bot_auth_token=token,
    )

    try:
        result = await self(request)
    except RpcError as e:
        if e.code == 303:
            await handle_migrate(self, e.value)
            result = await self(request)
        else:
            raise

    return await complete_login(self, result)


async def request_login_code(self: Client, phone: str) -> LoginToken:
    request = functions.auth.send_code(
        phone_number=phone,
        api_id=self._config.api_id,
        api_hash=self._config.api_hash,
        settings=types.CodeSettings(
            allow_flashcall=False,
            current_number=False,
            allow_app_hash=False,
            allow_missed_call=False,
            allow_firebase=False,
            logout_tokens=None,
            token=None,
            app_sandbox=None,
        ),
    )

    try:
        result = await self(request)
    except RpcError as e:
        if e.code == 303:
            await handle_migrate(self, e.value)
            result = await self(request)
        else:
            raise

    assert isinstance(result, types.auth.SentCode)
    return LoginToken._new(result, phone)


async def sign_in(
    self: Client, token: LoginToken, code: str
) -> Union[User, PasswordToken]:
    try:
        result = await self(
            functions.auth.sign_in(
                phone_number=token._phone,
                phone_code_hash=token._code.phone_code_hash,
                phone_code=code,
                email_verification=None,
            )
        )
    except RpcError as e:
        if e.name == "SESSION_PASSWORD_NEEDED":
            return await get_password_information(self)
        else:
            raise

    return await complete_login(self, result)


async def get_password_information(self: Client) -> PasswordToken:
    result = self(functions.account.get_password())
    assert isinstance(result, types.account.Password)
    return PasswordToken._new(result)


async def check_password(
    self: Client, token: PasswordToken, password: Union[str, bytes]
) -> User:
    self, token, password
    raise NotImplementedError


async def sign_out(self: Client) -> None:
    await self(functions.auth.log_out())


def session(self: Client) -> Session:
    self._config.session.state = self._message_box.session_state()
    return self._config.session
