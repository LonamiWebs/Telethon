from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from ...mtproto import RpcError
from ...session import Session
from ...session import User as SessionUser
from ...tl import abcs, functions, types
from ..types import LoginToken, PasswordToken, User
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


async def complete_login(client: Client, auth: abcs.auth.Authorization) -> User:
    assert isinstance(auth, types.auth.Authorization)
    assert isinstance(auth.user, types.User)
    user = User._from_raw(auth.user)
    client._config.session.user = SessionUser(
        id=user.id,
        dc=client._dc_id,
        bot=user.bot,
    )

    packed = user.pack()
    assert packed is not None
    client._chat_hashes.set_self_user(packed)

    try:
        state = await client(functions.updates.get_state())
        client._message_box.set_state(state)
    except Exception:
        pass

    return user


async def handle_migrate(client: Client, dc_id: Optional[int]) -> None:
    assert dc_id is not None
    sender = await connect_sender(dc_id, client._config)
    async with client._sender_lock:
        client._sender = sender
    client._dc_id = dc_id


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


async def get_password_information(client: Client) -> PasswordToken:
    result = client(functions.account.get_password())
    assert isinstance(result, types.account.Password)
    return PasswordToken._new(result)


async def check_password(
    self: Client, token: PasswordToken, password: Union[str, bytes]
) -> User:
    self, token, password
    raise NotImplementedError


async def sign_out(self: Client) -> None:
    await self(functions.auth.log_out())


def session(client: Client) -> Session:
    client._config.session.state = client._message_box.session_state()
    return client._config.session
