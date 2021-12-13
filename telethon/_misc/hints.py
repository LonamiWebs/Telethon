import datetime
import typing

from . import helpers
from .. import _tl
from ..types import _custom

Phone = str
Username = str
Entity = typing.Union[_tl.User, _tl.Chat, _tl.Channel]
FullEntity = typing.Union[_tl.UserFull, _tl.messages.ChatFull, _tl.ChatFull, _tl.ChannelFull]

EntityLike = typing.Union[
    Phone,
    Username,
    _tl.TypePeer,
    _tl.TypeInputPeer,
    Entity,
    FullEntity
]
EntitiesLike = typing.Union[EntityLike, typing.Sequence[EntityLike]]

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

# Can't use `typing.Type` in Python 3.5.2
# See https://github.com/python/typing/issues/266
try:
    OutFileLike = typing.Union[
        str,
        typing.Type[bytes],
        typing.BinaryIO
    ]
except TypeError:
    OutFileLike = typing.Union[
        str,
        typing.BinaryIO
    ]

MessageLike = typing.Union[str, _tl.Message]
MessageIDLike = typing.Union[int, _tl.Message, _tl.TypeInputMessage]

ProgressCallback = typing.Callable[[int, int], None]
