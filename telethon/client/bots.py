import typing

from .. import hints
from ..tl import types, functions, custom

if typing.TYPE_CHECKING:
    from .telegramclient import TelegramClient


class BotMethods:
    async def inline_query(
            self: 'TelegramClient',
            bot: 'hints.EntityLike',
            query: str,
            *,
            offset: str = None,
            geo_point: 'types.GeoPoint' = None) -> custom.InlineResults:
        """
        Makes an inline query to the specified bot (``@vote New Poll``).

        Arguments
            bot (`entity`):
                The bot entity to which the inline query should be made.

            query (`str`):
                The query that should be made to the bot.

            offset (`str`, optional):
                The string offset to use for the bot.

            geo_point (:tl:`GeoPoint`, optional)
                The geo point location information to send to the bot
                for localised results. Available under some bots.

        Returns
            A list of `custom.InlineResult
            <telethon.tl.custom.inlineresult.InlineResult>`.

        Example
            .. code-block:: python

                # Make an inline query to @like
                results = await client.inline_query('like', 'Do you like Telethon?')

                # Send the first result to some chat
                message = await results[0].click('TelethonOffTopic')
        """
        bot = await self.get_input_entity(bot)
        result = await self(functions.messages.GetInlineBotResultsRequest(
            bot=bot,
            peer=types.InputPeerEmpty(),
            query=query,
            offset=offset or '',
            geo_point=geo_point
        ))

        return custom.InlineResults(self, result)
