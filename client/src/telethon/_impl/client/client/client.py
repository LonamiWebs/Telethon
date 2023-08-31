from types import TracebackType
from typing import Optional, Type

from .account import edit_2fa, end_takeout, takeout
from .auth import log_out, qr_login, send_code_request, sign_in, sign_up, start
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
    connect,
    disconnect,
    disconnected,
    flood_sleep_threshold,
    is_connected,
    loop,
    set_proxy,
)
from .updates import (
    add_event_handler,
    catch_up,
    list_event_handlers,
    on,
    remove_event_handler,
    run_until_disconnected,
    set_receive_updates,
)
from .uploads import send_file, upload_file
from .users import (
    get_entity,
    get_input_entity,
    get_me,
    get_peer_id,
    is_bot,
    is_user_authorized,
)


class Client:
    def takeout(self) -> None:
        takeout(self)

    async def end_takeout(self) -> None:
        await end_takeout(self)

    async def edit_2fa(self) -> None:
        await edit_2fa(self)

    def start(self) -> None:
        start(self)

    async def sign_in(self) -> None:
        await sign_in(self)

    async def sign_up(self) -> None:
        await sign_up(self)

    async def send_code_request(self) -> None:
        await send_code_request(self)

    async def qr_login(self) -> None:
        await qr_login(self)

    async def log_out(self) -> None:
        await log_out(self)

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

    def run_until_disconnected(self) -> None:
        run_until_disconnected(self)

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

    async def is_bot(self) -> None:
        await is_bot(self)

    async def is_user_authorized(self) -> None:
        await is_user_authorized(self)

    async def get_entity(self) -> None:
        await get_entity(self)

    async def get_input_entity(self) -> None:
        await get_input_entity(self)

    async def get_peer_id(self) -> None:
        await get_peer_id(self)

    def loop(self) -> None:
        loop(self)

    def disconnected(self) -> None:
        disconnected(self)

    def flood_sleep_threshold(self) -> None:
        flood_sleep_threshold(self)

    async def connect(self) -> None:
        await connect(self)

    def is_connected(self) -> None:
        is_connected(self)

    def disconnect(self) -> None:
        disconnect(self)

    def set_proxy(self) -> None:
        set_proxy(self)

    async def __aenter__(self) -> None:
        raise NotImplementedError

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        exc_type, exc, tb
        raise NotImplementedError
