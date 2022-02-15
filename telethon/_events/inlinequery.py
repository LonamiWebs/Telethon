import inspect
import re

import asyncio

from .base import EventBuilder
from .._misc import utils
from .. import _tl
from ..types import _custom


class InlineQuery(EventBuilder, _custom.chatgetter.ChatGetter, _custom.sendergetter.SenderGetter):
    """
    Occurs whenever you sign in as a bot and a user
    sends an inline query such as ``@bot query``.

    Members:
        query (:tl:`UpdateBotInlineQuery`):
            The original :tl:`UpdateBotInlineQuery`.

            Make sure to access the `text` property of the query if
            you want the text rather than the actual query object.

        pattern_match (`obj`, optional):
            The resulting object from calling the passed ``pattern``
            function, which is ``re.compile(...).match`` by default.

    Example
        .. code-block:: python

            from telethon import events

            @client.on(events.InlineQuery)
            async def handler(event):
                builder = event.builder

                # Two options (convert user text to UPPERCASE or lowercase)
                await event.answer([
                    builder.article('UPPERCASE', text=event.text.upper()),
                    builder.article('lowercase', text=event.text.lower()),
                ])
    """
    @classmethod
    def _build(cls, client, update, entities):
        if not isinstance(update, _tl.UpdateBotInlineQuery):
            return None

        self = cls.__new__(cls)
        self._client = client
        self._sender = entities.get(_tl.PeerUser(update.user_id))
        self._chat = entities.get(_tl.PeerUser(update.user_id))
        self.query = update
        self.pattern_match = None
        self._answered = False
        return self

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
        The string the user's client used as an offset for the query.
        This will either be empty or equal to offsets passed to `answer`.
        """
        return self.query.offset

    @property
    def geo(self):
        """
        If the user location is requested when using inline mode
        and the user's device is able to send it, this will return
        the :tl:`GeoPoint` with the position of the user.
        """
        return self.query.geo

    @property
    def builder(self):
        """
        Returns a new `InlineBuilder
        <telethon.tl.custom.inlinebuilder.InlineBuilder>` instance.

        See the documentation for `builder` to know what kind of answers
        can be given.
        """
        return _custom.InlineBuilder(self._client)

    async def answer(
            self, results=None, cache_time=0, *,
            gallery=False, next_offset=None, private=False,
            switch_pm=None, switch_pm_param=''):
        """
        Answers the inline query with the given results.

        Args:
            results (`list`, optional):
                A list of :tl:`InputBotInlineResult` to use.
                You should use `builder` to create these:

                .. code-block:: python

                    builder = inline.builder
                    r1 = builder.article('Be nice', text='Have a nice day')
                    r2 = builder.article('Be bad', text="I don't like you")
                    await inline.answer([r1, r2])

                You can send up to 50 results as documented in
                https://core.telegram.org/bots/api#answerinlinequery.
                Sending more will raise ``ResultsTooMuchError``,
                and you should consider using `next_offset` to
                paginate them.

            cache_time (`int`, optional):
                For how long this result should be cached on
                the user's client. Defaults to 0 for no cache.

            gallery (`bool`, optional):
                Whether the results should show as a gallery (grid) or not.

            next_offset (`str`, optional):
                The offset the client will send when the user scrolls the
                results and it repeats the request.

            private (`bool`, optional):
                Whether the results should be cached by Telegram
                (not private) or by the user's client (private).

            switch_pm (`str`, optional):
                If set, this text will be shown in the results
                to allow the user to switch to private messages.

            switch_pm_param (`str`, optional):
                Optional parameter to start the bot with if
                `switch_pm` was used.

        Example:

            .. code-block:: python

                @bot.on(events.InlineQuery)
                async def handler(event):
                    builder = event.builder

                    rev_text = event.text[::-1]
                    await event.answer([
                        builder.article('Reverse text', text=rev_text),
                        builder.photo('/path/to/photo.jpg')
                    ])
        """
        if self._answered:
            return

        if results:
            futures = [self._as_future(x) for x in results]

            await asyncio.wait(futures)

            # All futures will be in the `done` *set* that `wait` returns.
            #
            # Precisely because it's a `set` and not a `list`, it
            # will not preserve the order, but since all futures
            # completed we can use our original, ordered `list`.
            results = [x.result() for x in futures]
        else:
            results = []

        if switch_pm:
            switch_pm = _tl.InlineBotSwitchPM(switch_pm, switch_pm_param)

        return await self._client(
            _tl.fn.messages.SetInlineBotResults(
                query_id=self.query.query_id,
                results=results,
                cache_time=cache_time,
                gallery=gallery,
                next_offset=next_offset,
                private=private,
                switch_pm=switch_pm
            )
        )

    @staticmethod
    def _as_future(obj):
        if inspect.isawaitable(obj):
            return asyncio.ensure_future(obj)

        f = asyncio.get_running_loop().create_future()
        f.set_result(obj)
        return f
