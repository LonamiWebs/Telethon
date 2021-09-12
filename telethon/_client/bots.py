import typing

from .. import hints, _tl
from .._tl import custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


async def inline_query(
        self: 'TelegramClient',
        bot: 'hints.EntityLike',
        query: str,
        *,
        entity: 'hints.EntityLike' = None,
        offset: str = None,
        geo_point: '_tl.GeoPoint' = None) -> custom.InlineResults:
    bot = await self.get_input_entity(bot)
    if entity:
        peer = await self.get_input_entity(entity)
    else:
        peer = _tl.InputPeerEmpty()

    result = await self(_tl.fn.messages.GetInlineBotResults(
        bot=bot,
        peer=peer,
        query=query,
        offset=offset or '',
        geo_point=geo_point
    ))

    return custom.InlineResults(self, result, entity=peer if entity else None)
