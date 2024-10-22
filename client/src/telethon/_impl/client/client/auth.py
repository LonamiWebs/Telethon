from __future__ import annotations

import getpass
import re
from typing import TYPE_CHECKING, Optional

from ...crypto import two_factor_auth
from ...mtproto import RpcError
from ...session import DataCenter
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
    assert client._sender
    assert isinstance(auth, types.auth.Authorization)
    assert isinstance(auth.user, types.User)
    user = User._from_raw(auth.user)
    client._session.user = SessionUser(
        id=user.id, dc=client._sender.dc_id, bot=user.bot, username=user.username
    )

    client._chat_hashes.set_self_user(user.id, user.bot)

    try:
        state = await client(functions.updates.get_state())
        client._message_box.set_state(state)
        client._session.state = client._message_box.session_state()
    except Exception:
        pass

    try:
        await client._storage.save(client._session)
    except Exception:
        client._config.base_logger.exception(
            "failed to save session upon login; you may need to login again in future runs"
        )

    return user


async def handle_migrate(client: Client, dc_id: Optional[int]) -> None:
    assert client._sender
    assert dc_id is not None
    sender, client._session.dcs = await connect_sender(
        client._config, client._session.dcs, DataCenter(id=dc_id)
    )

    old_sender = client._sender
    client._sender = sender
    await old_sender.disconnect()


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


async def sign_in(self: Client, token: LoginToken, code: str) -> User | PasswordToken:
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


async def interactive_login(
    self: Client,
    phone_or_token: Optional[str] = None,
    *,
    password: Optional[str] = None,
) -> User:
    if me := await self.get_me():
        return me

    if not phone_or_token:
        phone_or_token = ""
        while not re.match(r"\+?[\s()]*\d", phone_or_token):
            print("Please enter your phone (+1 23...) or bot token (12:abcd...)")
            phone_or_token = input(": ").strip()

    # Bot flow
    if re.match(r"\d+:", phone_or_token):
        user = await self.bot_sign_in(phone_or_token)
        try:
            print("Signed in as bot:", user.name)
        except UnicodeEncodeError:
            print("Signed in as bot")

        return user

    # User flow
    login_token = await self.request_login_code(phone_or_token)

    while True:
        code = input("Please enter the code you received: ")
        try:
            user_or_token = await self.sign_in(login_token, code)
        except RpcError as e:
            if e.name.startswith("PHONE_CODE"):
                print("Invalid code:", e)
            else:
                raise
        else:
            break

    if isinstance(user_or_token, PasswordToken):
        if password:
            user = await self.check_password(user_or_token, password)
        else:
            while True:
                print(
                    "Please enter your password (prompt is hidden; type and press enter)"
                )
                password = getpass.getpass(": ")
                try:
                    user = await self.check_password(user_or_token, password)
                    break
                except RpcError as e:
                    if e.name.startswith("PASSWORD"):
                        print("Invalid password:", e)
                    else:
                        raise
    else:
        user = user_or_token

    try:
        print("Signed in as user:", user.name)
    except UnicodeEncodeError:
        print("Signed in as user")

    print("Remember to not break the ToS or you will risk an account ban!")
    print("https://telegram.org/tos & https://core.telegram.org/api/terms")
    return user


async def get_password_information(client: Client) -> PasswordToken:
    result = await client(functions.account.get_password())
    assert isinstance(result, types.account.Password)
    return PasswordToken._new(result)


async def check_password(
    self: Client, token: PasswordToken, password: str | bytes
) -> User:
    algo = token._password.current_algo
    if not isinstance(
        algo, types.PasswordKdfAlgoSha256Sha256Pbkdf2HmacshA512Iter100000Sha256ModPow
    ):
        raise RuntimeError("unrecognised 2FA algorithm")

    if not two_factor_auth.check_p_and_g(algo.p, algo.g):
        token = await get_password_information(self)
        algo = token._password.current_algo
        if not isinstance(
            algo,
            types.PasswordKdfAlgoSha256Sha256Pbkdf2HmacshA512Iter100000Sha256ModPow,
        ):
            raise RuntimeError("unrecognised 2FA algorithm")
        if not two_factor_auth.check_p_and_g(algo.p, algo.g):
            raise RuntimeError("failed to get correct password information")

    assert token._password.srp_id is not None
    assert token._password.srp_B is not None

    two_fa = two_factor_auth.calculate_2fa(
        salt1=algo.salt1,
        salt2=algo.salt2,
        g=algo.g,
        p=algo.p,
        g_b=token._password.srp_B,
        a=token._password.secure_random,
        password=password.encode("utf-8") if isinstance(password, str) else password,
    )

    result = await self(
        functions.auth.check_password(
            password=types.InputCheckPasswordSrp(
                srp_id=token._password.srp_id,
                A=two_fa.g_a,
                M1=two_fa.m1,
            )
        )
    )

    return await complete_login(self, result)


async def sign_out(self: Client) -> None:
    await self(functions.auth.log_out())

    self._chat_hashes.clear()
    self._message_box.reset()

    self._session.user = None
    self._session.state = None
    await self._storage.save(self._session)
