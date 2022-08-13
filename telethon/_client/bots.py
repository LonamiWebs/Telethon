import typing
import asyncio

from ..types import _custom
from .._misc import hints
from .. import errors, _tl

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


async def inline_query(
        self: 'TelegramClient',
        bot: 'hints.DialogLike',
        query: str,
        *,
        dialog: 'hints.DialogLike' = None,
        offset: str = None,
        geo_point: '_tl.GeoPoint' = None) -> _custom.InlineResults:
    bot = await self._get_input_peer(bot)
    if dialog:
        peer = await self._get_input_peer(dialog)
    else:
        peer = _tl.InputPeerEmpty()

    try:
        result = await self(_tl.fn.messages.GetInlineBotResults(
            bot=bot,
            peer=peer,
            query=query,
            offset=offset or '',
            geo_point=geo_point
        ))
    except errors.BotResponseTimeoutError:
        raise asyncio.TimeoutError from None

    return _custom.InlineResults(self, result, entity=peer if dialog else None)
