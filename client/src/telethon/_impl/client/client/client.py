import asyncio
from collections import deque
from types import TracebackType
from typing import Deque, Optional, Self, Type, TypeVar, Union

from ...mtsender.sender import Sender
from ...session.chat.hash_cache import ChatHashCache
from ...session.message_box.messagebox import MessageBox
from ...tl import abcs
from ...tl.core.request import Request
from ..types.chat.user import User
from ..types.login_token import LoginToken
from ..types.password_token import PasswordToken
from .account import edit_2fa, end_takeout, takeout
from .auth import (
    bot_sign_in,
    check_password,
    is_authorized,
    request_login_code,
    sign_in,
    sign_out,
)
from .bots import inline_query
from .buttons import build_reply_markup
from .chats import (
    action,
    edit_admin,
    edit_permissions,
    get_permissions,
    get_stats,
    iter_admin_log,
    iter_participants,
    iter_profile_photos,
    kick_participant,
)
from .dialogs import conversation, delete_dialog, edit_folder, iter_dialogs, iter_drafts
from .downloads import download_media, download_profile_photo, iter_download
from .messages import (
    delete_messages,
    edit_message,
    forward_messages,
    iter_messages,
    pin_message,
    send_message,
    send_read_acknowledge,
    unpin_message,
)
from .net import (
    DEFAULT_DC,
    Config,
    connect,
    connected,
    disconnect,
    invoke_request,
    run_until_disconnected,
    step,
)
from .updates import (
    add_event_handler,
    catch_up,
    list_event_handlers,
    on,
    remove_event_handler,
    set_receive_updates,
)
from .uploads import send_file, upload_file
from .users import get_entity, get_input_entity, get_me, get_peer_id

Return = TypeVar("Return")


class Client:
    def __init__(self, config: Config) -> None:
        self._sender: Optional[Sender] = None
        self._sender_lock = asyncio.Lock()
        self._dc_id = DEFAULT_DC
        self._config = config
        self._message_box = MessageBox()
        self._chat_hashes = ChatHashCache(None)
        self._last_update_limit_warn = None
        self._updates: Deque[abcs.Update] = deque(maxlen=config.update_queue_limit)
        self._downloader_map = object()

        if self_user := config.session.user:
            self._dc_id = self_user.dc
            if config.catch_up and config.session.state:
                self._message_box.load(config.session.state)

    def takeout(self) -> None:
        takeout(self)

    async def end_takeout(self) -> None:
        await end_takeout(self)

    async def edit_2fa(self) -> None:
        await edit_2fa(self)

    async def is_authorized(self) -> bool:
        return await is_authorized(self)

    async def bot_sign_in(self, token: str) -> User:
        return await bot_sign_in(self, token)

    async def request_login_code(self, phone: str) -> LoginToken:
        return await request_login_code(self, phone)

    async def sign_in(self, token: LoginToken, code: str) -> Union[User, PasswordToken]:
        return await sign_in(self, token, code)

    async def check_password(
        self, token: PasswordToken, password: Union[str, bytes]
    ) -> User:
        return await check_password(self, token, password)

    async def sign_out(self) -> None:
        await sign_out(self)

    async def inline_query(self) -> None:
        await inline_query(self)

    def build_reply_markup(self) -> None:
        build_reply_markup(self)

    def iter_participants(self) -> None:
        iter_participants(self)

    def iter_admin_log(self) -> None:
        iter_admin_log(self)

    def iter_profile_photos(self) -> None:
        iter_profile_photos(self)

    def action(self) -> None:
        action(self)

    async def edit_admin(self) -> None:
        await edit_admin(self)

    async def edit_permissions(self) -> None:
        await edit_permissions(self)

    async def kick_participant(self) -> None:
        await kick_participant(self)

    async def get_permissions(self) -> None:
        await get_permissions(self)

    async def get_stats(self) -> None:
        await get_stats(self)

    def iter_dialogs(self) -> None:
        iter_dialogs(self)

    def iter_drafts(self) -> None:
        iter_drafts(self)

    async def edit_folder(self) -> None:
        await edit_folder(self)

    async def delete_dialog(self) -> None:
        await delete_dialog(self)

    def conversation(self) -> None:
        conversation(self)

    async def download_profile_photo(self) -> None:
        await download_profile_photo(self)

    async def download_media(self) -> None:
        await download_media(self)

    def iter_download(self) -> None:
        iter_download(self)

    def iter_messages(self) -> None:
        iter_messages(self)

    async def send_message(self) -> None:
        await send_message(self)

    async def forward_messages(self) -> None:
        await forward_messages(self)

    async def edit_message(self) -> None:
        await edit_message(self)

    async def delete_messages(self) -> None:
        await delete_messages(self)

    async def send_read_acknowledge(self) -> None:
        await send_read_acknowledge(self)

    async def pin_message(self) -> None:
        await pin_message(self)

    async def unpin_message(self) -> None:
        await unpin_message(self)

    async def set_receive_updates(self) -> None:
        await set_receive_updates(self)

    def on(self) -> None:
        on(self)

    def add_event_handler(self) -> None:
        add_event_handler(self)

    def remove_event_handler(self) -> None:
        remove_event_handler(self)

    def list_event_handlers(self) -> None:
        list_event_handlers(self)

    async def catch_up(self) -> None:
        await catch_up(self)

    async def send_file(self) -> None:
        await send_file(self)

    async def upload_file(self) -> None:
        await upload_file(self)

    async def get_me(self) -> None:
        await get_me(self)

    async def get_entity(self) -> None:
        await get_entity(self)

    async def get_input_entity(self) -> None:
        await get_input_entity(self)

    async def get_peer_id(self) -> None:
        await get_peer_id(self)

    async def connect(self) -> None:
        await connect(self)

    async def disconnect(self) -> None:
        await disconnect(self)

    async def __call__(self, request: Request[Return]) -> Return:
        if not self._sender:
            raise ConnectionError("not connected")

        return await invoke_request(self, self._sender, self._sender_lock, request)

    async def step(self) -> None:
        await step(self)

    async def run_until_disconnected(self) -> None:
        await run_until_disconnected(self)

    @property
    def connected(self) -> bool:
        return connected(self)

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        exc_type, exc, tb
        await self.disconnect()
