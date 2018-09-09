import inspect
import re

import asyncio

from .common import EventBuilder, EventCommon, name_inner_event
from .. import utils
from ..tl import types, functions, custom
from ..tl.custom.sendergetter import SenderGetter


@name_inner_event
class InlineQuery(EventBuilder):
    """
    Represents an inline query event (when someone writes ``'@my_bot query'``).

    Args:
        users (`entity`, optional):
            May be one or more entities (username/peer/etc.), preferably IDs.
            By default, only inline queries from these users will be handled.

        blacklist_users (`bool`, optional):
            Whether to treat the users as a blacklist instead of
            as a whitelist (default). This means that every chat
            will be handled *except* those specified in ``users``
            which will be ignored if ``blacklist_users=True``.

        pattern (`str`, `callable`, `Pattern`, optional):
            If set, only queries matching this pattern will be handled.
            You can specify a regex-like string which will be matched
            against the message, a callable function that returns ``True``
            if a message is acceptable, or a compiled regex pattern.
    """
    def __init__(
            self, users=None, *, blacklist_users=False, func=None, pattern=None):
        super().__init__(users, blacklist_chats=blacklist_users, func=func)

        if isinstance(pattern, str):
            self.pattern = re.compile(pattern).match
        elif not pattern or callable(pattern):
            self.pattern = pattern
        elif hasattr(pattern, 'match') and callable(pattern.match):
            self.pattern = pattern.match
        else:
            raise TypeError('Invalid pattern type given')

    @classmethod
    def build(cls, update):
        if isinstance(update, types.UpdateBotInlineQuery):
            event = cls.Event(update)
        else:
            return

        event._entities = update._entities
        return event

    def filter(self, event):
        if self.pattern:
            match = self.pattern(event.text)
            if not match:
                return
            event.pattern_match = match

        return super().filter(event)

    class Event(EventCommon, SenderGetter):
        """
        Represents the event of a new callback query.

        Members:
            query (:tl:`UpdateBotCallbackQuery`):
                The original :tl:`UpdateBotCallbackQuery`.

            pattern_match (`obj`, optional):
                The resulting object from calling the passed ``pattern``
                function, which is ``re.compile(...).match`` by default.
        """
        def __init__(self, query):
            super().__init__(chat_peer=types.PeerUser(query.user_id))
            self.query = query
            self.pattern_match = None
            self._answered = False
            self._sender_id = query.user_id
            self._input_sender = None
            self._sender = None

        @property
        def id(self):
            """
            Returns the unique identifier for the query ID.
            """
            return self.query.query_id

        @property
        def text(self):
            """
            Returns the text the user used to make the inline query.
            """
            return self.query.query

        @property
        def offset(self):
            """
            ???
            """
            return self.query.offset

        @property
        def geo(self):
            """
            If the user location is requested when using inline mode
            and the user's device is able to send it, this will return
            the :tl:`GeoPoint` with the position of the user.
            """
            return

        @property
        def builder(self):
            """
            Returns a new `inline result builder
            <telethon.tl.custom.inline.InlineBuilder>`.
            """
            return custom.InlineBuilder(self._client)

        async def answer(
                self, results=None, cache_time=0, *,
                gallery=False, private=False,
                switch_pm=None, switch_pm_param=''):
            """
            Answers the inline query with the given results.

            Args:
                results (`list`, optional):
                    A list of :tl:`InputBotInlineResult` to use.
                    You should use `builder` to create these:

                    .. code-block: python

                        builder = inline.builder
                        r1 = builder.article('Be nice', text='Have a nice day')
                        r2 = builder.article('Be bad', text="I don't like you")
                        await inline.answer([r1, r2])

                cache_time (`int`, optional):
                    For how long this result should be cached on
                    the user's client. Defaults to 0 for no cache.

                gallery (`bool`, optional):
                    Whether the results should show as a gallery (grid) or not.

                private (`bool`, optional):
                    Whether the results should be cached by Telegram
                    (not private) or by the user's client (private).

                switch_pm (`str`, optional):
                    If set, this text will be shown in the results
                    to allow the user to switch to private messages.

                switch_pm_param (`str`, optional):
                    Optional parameter to start the bot with if
                    `switch_pm` was used.
            """
            if self._answered:
                return

            results = [self._as_awaitable(x, self._client.loop)
                       for x in results]

            done, _ = await asyncio.wait(results, loop=self._client.loop)
            results = [x.result() for x in done]

            if switch_pm:
                switch_pm = types.InlineBotSwitchPM(switch_pm, switch_pm_param)

            return await self._client(
                functions.messages.SetInlineBotResultsRequest(
                    query_id=self.query.query_id,
                    results=results,
                    cache_time=cache_time,
                    gallery=gallery,
                    private=private,
                    switch_pm=switch_pm
                )
            )

        @staticmethod
        def _as_awaitable(obj, loop):
            if inspect.isawaitable(obj):
                return obj

            f = loop.create_future()
            f.set_result(obj)
            return f
