import asyncio
import datetime
from collections import deque
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Deque,
    Dict,
    List,
    Literal,
    Optional,
    Self,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from ...mtsender import Sender
from ...session import ChatHashCache, MessageBox, PackedChat, Session
from ...tl import Request, abcs
from ..events import Event
from ..events.filters import Filter
from ..types import (
    AsyncList,
    Chat,
    ChatLike,
    File,
    InFileLike,
    LoginToken,
    MediaLike,
    Message,
    OutFileLike,
    PasswordToken,
    User,
)
from .account import edit_2fa, end_takeout, takeout
from .auth import (
    bot_sign_in,
    check_password,
    is_authorized,
    request_login_code,
    session,
    sign_in,
    sign_out,
)
from .bots import InlineResult, inline_query
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
from .files import (
    download,
    iter_download,
    send_audio,
    send_file,
    send_photo,
    send_video,
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
    search_all_messages,
    search_messages,
    send_message,
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
)
from .updates import (
    add_event_handler,
    get_handler_filter,
    on,
    remove_event_handler,
    set_handler_filter,
)
from .users import (
    get_entity,
    get_input_entity,
    get_me,
    get_peer_id,
    input_to_peer,
    is_bot,
    is_user_authorized,
    resolve_to_packed,
)

Return = TypeVar("Return")
T = TypeVar("T")


class Client:
    def __init__(self, config: Config) -> None:
        self._sender: Optional[Sender] = None
        self._sender_lock = asyncio.Lock()
        self._dc_id = DEFAULT_DC
        self._config = config
        self._message_box = MessageBox()
        self._chat_hashes = ChatHashCache(None)
        self._last_update_limit_warn: Optional[float] = None
        self._updates: asyncio.Queue[
            Tuple[abcs.Update, Dict[int, Union[abcs.User, abcs.Chat]]]
        ] = asyncio.Queue(maxsize=config.update_queue_limit or 0)
        self._dispatcher: Optional[asyncio.Task[None]] = None
        self._downloader_map = object()
        self._handlers: Dict[
            Type[Event], List[Tuple[Callable[[Any], Awaitable[Any]], Optional[Filter]]]
        ] = {}

        if self_user := config.session.user:
            self._dc_id = self_user.dc
            if config.catch_up and config.session.state:
                self._message_box.load(config.session.state)

    def action(self) -> None:
        action(self)

    def add_event_handler(
        self,
        handler: Callable[[Event], Awaitable[Any]],
        event_cls: Type[Event],
        filter: Optional[Filter] = None,
    ) -> None:
        add_event_handler(self, handler, event_cls, filter)

    async def bot_sign_in(self, token: str) -> User:
        return await bot_sign_in(self, token)

    def build_reply_markup(self) -> None:
        build_reply_markup(self)

    async def check_password(
        self, token: PasswordToken, password: Union[str, bytes]
    ) -> User:
        return await check_password(self, token, password)

    async def connect(self) -> None:
        await connect(self)

    def conversation(self) -> None:
        conversation(self)

    async def delete_dialog(self) -> None:
        await delete_dialog(self)

    async def delete_messages(
        self, chat: ChatLike, message_ids: List[int], *, revoke: bool = True
    ) -> int:
        return await delete_messages(self, chat, message_ids, revoke=revoke)

    async def disconnect(self) -> None:
        await disconnect(self)

    async def download(self, media: MediaLike, file: OutFileLike) -> None:
        """
        Download a file.

        This is simply a more convenient method to `iter_download`,
        as it will handle dealing with the file chunks and writes by itself.
        """
        await download(self, media, file)

    async def edit_2fa(self) -> None:
        await edit_2fa(self)

    async def edit_admin(self) -> None:
        await edit_admin(self)

    async def edit_folder(self) -> None:
        await edit_folder(self)

    async def edit_message(
        self,
        chat: ChatLike,
        message_id: int,
        *,
        text: Optional[str] = None,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: Optional[bool] = None,
    ) -> Message:
        return await edit_message(
            self,
            chat,
            message_id,
            text=text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
        )

    async def edit_permissions(self) -> None:
        await edit_permissions(self)

    async def end_takeout(self) -> None:
        await end_takeout(self)

    async def forward_messages(
        self, target: ChatLike, message_ids: List[int], source: ChatLike
    ) -> List[Message]:
        return await forward_messages(self, target, message_ids, source)

    async def get_entity(self) -> None:
        await get_entity(self)

    def get_handler_filter(
        self, handler: Callable[[Event], Awaitable[Any]]
    ) -> Optional[Filter]:
        return get_handler_filter(self, handler)

    async def get_input_entity(self) -> None:
        await get_input_entity(self)

    async def get_me(self) -> None:
        await get_me(self)

    def get_messages(
        self,
        chat: ChatLike,
        limit: Optional[int] = None,
        *,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        return get_messages(
            self, chat, limit, offset_id=offset_id, offset_date=offset_date
        )

    def get_messages_with_ids(
        self, chat: ChatLike, message_ids: List[int]
    ) -> AsyncList[Message]:
        return get_messages_with_ids(self, chat, message_ids)

    async def get_peer_id(self) -> None:
        await get_peer_id(self)

    async def get_permissions(self) -> None:
        await get_permissions(self)

    async def get_stats(self) -> None:
        await get_stats(self)

    async def inline_query(
        self, bot: ChatLike, query: str, *, chat: Optional[ChatLike] = None
    ) -> AsyncIterator[InlineResult]:
        return await inline_query(self, bot, query, chat=chat)

    async def is_authorized(self) -> bool:
        return await is_authorized(self)

    async def is_bot(self) -> None:
        await is_bot(self)

    async def is_user_authorized(self) -> None:
        await is_user_authorized(self)

    def iter_admin_log(self) -> None:
        iter_admin_log(self)

    def iter_dialogs(self) -> None:
        iter_dialogs(self)

    async def iter_download(self) -> None:
        """
        Stream server media by iterating over its bytes in chunks.
        """
        await iter_download(self)

    def iter_drafts(self) -> None:
        iter_drafts(self)

    def iter_participants(self) -> None:
        iter_participants(self)

    def iter_profile_photos(self) -> None:
        iter_profile_photos(self)

    async def kick_participant(self) -> None:
        await kick_participant(self)

    def on(
        self, event_cls: Type[Event], filter: Optional[Filter] = None
    ) -> Callable[
        [Callable[[Event], Awaitable[Any]]], Callable[[Event], Awaitable[Any]]
    ]:
        return on(self, event_cls, filter)

    async def pin_message(self, chat: ChatLike, message_id: int) -> Message:
        return await pin_message(self, chat, message_id)

    def remove_event_handler(self, handler: Callable[[Event], Awaitable[Any]]) -> None:
        remove_event_handler(self, handler)

    async def request_login_code(self, phone: str) -> LoginToken:
        return await request_login_code(self, phone)

    async def resolve_to_packed(self, chat: ChatLike) -> PackedChat:
        return await resolve_to_packed(self, chat)

    async def run_until_disconnected(self) -> None:
        await run_until_disconnected(self)

    def search_all_messages(
        self,
        limit: Optional[int] = None,
        *,
        query: Optional[str] = None,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        return search_all_messages(
            self, limit, query=query, offset_id=offset_id, offset_date=offset_date
        )

    def search_messages(
        self,
        chat: ChatLike,
        limit: Optional[int] = None,
        *,
        query: Optional[str] = None,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime.datetime] = None,
    ) -> AsyncList[Message]:
        return search_messages(
            self, chat, limit, query=query, offset_id=offset_id, offset_date=offset_date
        )

    async def send_audio(
        self,
        chat: ChatLike,
        path: Optional[Union[str, Path, File]] = None,
        *,
        url: Optional[str] = None,
        file: Optional[InFileLike] = None,
        size: Optional[int] = None,
        name: Optional[str] = None,
        duration: Optional[float] = None,
        voice: bool = False,
        title: Optional[str] = None,
        performer: Optional[str] = None,
    ) -> Message:
        """
        Send an audio file.

        Unlike `send_file`, this method will attempt to guess the values for
        duration, title and performer if they are not provided.
        """
        return await send_audio(
            self,
            chat,
            path,
            url=url,
            file=file,
            size=size,
            name=name,
            duration=duration,
            voice=voice,
            title=title,
            performer=performer,
        )

    async def send_file(
        self,
        chat: ChatLike,
        path: Optional[Union[str, Path, File]] = None,
        *,
        url: Optional[str] = None,
        file: Optional[InFileLike] = None,
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
    ) -> Message:
        """
        Send any type of file with any amount of attributes.

        This method will not attempt to guess any of the file metadata such as
        width, duration, title, etc. If you want to let the library attempt to
        guess the file metadata, use the type-specific methods to send media:
        `send_photo`, `send_audio` or `send_file`.

        Unlike `send_photo`, image files will be sent as documents by default.

        The parameters are used to construct a `File`. See the documentation
        for `File.new` to learn what they do and when they are in effect.
        """
        return await send_file(
            self,
            chat,
            path,
            url=url,
            file=file,
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
        )

    async def send_message(
        self,
        chat: ChatLike,
        *,
        text: Optional[str] = None,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        link_preview: Optional[bool] = None,
    ) -> Message:
        return await send_message(
            self,
            chat,
            text=text,
            markdown=markdown,
            html=html,
            link_preview=link_preview,
        )

    async def send_photo(
        self,
        chat: ChatLike,
        path: Optional[Union[str, Path, File]] = None,
        *,
        url: Optional[str] = None,
        file: Optional[InFileLike] = None,
        size: Optional[int] = None,
        name: Optional[str] = None,
        compress: bool = True,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Message:
        """
        Send a photo file.

        Exactly one of path, url or file must be specified.
        A `File` can also be used as the second parameter.

        By default, the server will be allowed to `compress` the image.
        Only compressed images can be displayed as photos in applications.
        Images that cannot be compressed will be sent as file documents,
        with a thumbnail if possible.

        Unlike `send_file`, this method will attempt to guess the values for
        width and height if they are not provided and the can't be compressed.
        """
        return await send_photo(
            self,
            chat,
            path,
            url=url,
            file=file,
            size=size,
            name=name,
            compress=compress,
            width=width,
            height=height,
        )

    async def send_video(
        self,
        chat: ChatLike,
        path: Optional[Union[str, Path, File]] = None,
        *,
        url: Optional[str] = None,
        file: Optional[InFileLike] = None,
        size: Optional[int] = None,
        name: Optional[str] = None,
        duration: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        round: bool = False,
        supports_streaming: bool = False,
    ) -> Message:
        """
        Send a video file.

        Unlike `send_file`, this method will attempt to guess the values for
        duration, width and height if they are not provided.
        """
        return await send_video(
            self,
            chat,
            path,
            url=url,
            file=file,
            size=size,
            name=name,
            duration=duration,
            width=width,
            height=height,
            round=round,
            supports_streaming=supports_streaming,
        )

    def set_handler_filter(
        self,
        handler: Callable[[Event], Awaitable[Any]],
        filter: Optional[Filter] = None,
    ) -> None:
        set_handler_filter(self, handler, filter)

    async def sign_in(self, token: LoginToken, code: str) -> Union[User, PasswordToken]:
        return await sign_in(self, token, code)

    async def sign_out(self) -> None:
        await sign_out(self)

    def takeout(self) -> None:
        takeout(self)

    async def unpin_message(
        self, chat: ChatLike, message_id: Union[int, Literal["all"]]
    ) -> None:
        await unpin_message(self, chat, message_id)

    @property
    def connected(self) -> bool:
        return connected(self)

    @property
    def session(self) -> Session:
        """
        Up-to-date session state, useful for persisting it to storage.

        Mutating the returned object may cause the library to misbehave.
        """
        return session(self)

    def _build_message_map(
        self,
        result: abcs.Updates,
        peer: Optional[abcs.InputPeer],
    ) -> MessageMap:
        return build_message_map(self, result, peer)

    async def _resolve_to_packed(self, chat: ChatLike) -> PackedChat:
        return await resolve_to_packed(self, chat)

    def _input_to_peer(self, input: Optional[abcs.InputPeer]) -> Optional[abcs.Peer]:
        return input_to_peer(self, input)

    async def __call__(self, request: Request[Return]) -> Return:
        if not self._sender:
            raise ConnectionError("not connected")

        return await invoke_request(self, self._sender, self._sender_lock, request)

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
