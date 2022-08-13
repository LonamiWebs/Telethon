import datetime
import typing

from . import helpers
from .. import _tl
from ..types import _custom

Phone = str
Username = str
PeerID = int
Dialog = typing.Union[_tl.User, _tl.Chat, _tl.Channel]
FullDialog = typing.Union[_tl.UserFull, _tl.messages.ChatFull, _tl.ChatFull, _tl.ChannelFull]

DialogLike = typing.Union[
    Phone,
    Username,
    PeerID,
    _tl.TypePeer,
    _tl.TypeInputPeer,
    Dialog,
    FullDialog
]
DialogsLike = typing.Union[DialogLike, typing.Sequence[DialogLike]]

ButtonLike = typing.Union[_tl.TypeKeyboardButton, _custom.Button]
MarkupLike = typing.Union[
    _tl.TypeReplyMarkup,
    ButtonLike,
    typing.Sequence[ButtonLike],
    typing.Sequence[typing.Sequence[ButtonLike]]
]

TotalList = helpers.TotalList

DateLike = typing.Optional[typing.Union[float, datetime.datetime, datetime.date, datetime.timedelta]]

LocalPath = str
ExternalUrl = str
BotFileID = str
FileLike = typing.Union[
    LocalPath,
    ExternalUrl,
    BotFileID,
    bytes,
    typing.BinaryIO,
    _tl.TypeMessageMedia,
    _tl.TypeInputFile,
    _tl.TypeInputFileLocation
]

OutFileLike = typing.Union[
    str,
    typing.Type[bytes],
    typing.BinaryIO
]

MessageLike = typing.Union[str, _tl.Message]
MessageIDLike = typing.Union[int, _tl.Message, _tl.TypeInputMessage]

ProgressCallback = typing.Callable[[int, int], None]
