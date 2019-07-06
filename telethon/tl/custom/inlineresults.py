import time

from .inlineresult import InlineResult


class InlineResults(list):
    """
    Custom class that encapsulates :tl:`BotResults` providing
    an abstraction to easily access some commonly needed features
    (such as clicking one of the results to select it)

    Note that this is a list of `InlineResult
    <telethon.tl.custom.inlineresult.InlineResult>`
    so you can iterate over it or use indices to
    access its elements. In addition, it has some
    attributes.

    Attributes:
        result (:tl:`BotResults`):
            The original :tl:`BotResults` object.

        query_id (`int`):
            The random ID that identifies this query.

        cache_time (`int`):
            For how long the results should be considered
            valid. You can call `results_valid` at any
            moment to determine if the results are still
            valid or not.

        users (:tl:`User`):
            The users present in this inline query.

        gallery (`bool`):
            Whether these results should be presented
            in a grid (as a gallery of images) or not.

        next_offset (`str`, optional):
            The string to be used as an offset to get
            the next chunk of results, if any.

        switch_pm (:tl:`InlineBotSwitchPM`, optional):
            If presents, the results should show a button to
            switch to a private conversation with the bot using
            the text in this object.
    """
    def __init__(self, client, original):
        super().__init__(InlineResult(client, x, original.query_id)
                         for x in original.results)

        self.result = original
        self.query_id = original.query_id
        self.cache_time = original.cache_time
        self._valid_until = time.time() + self.cache_time
        self.users = original.users
        self.gallery = bool(original.gallery)
        self.next_offset = original.next_offset
        self.switch_pm = original.switch_pm

    def results_valid(self):
        """
        Returns `True` if the cache time has not expired
        yet and the results can still be considered valid.
        """
        return time.time() < self._valid_until

    def _to_str(self, item_function):
        return ('[{}, query_id={}, cache_time={}, users={}, gallery={}, '
                'next_offset={}, switch_pm={}]'.format(
            ', '.join(item_function(x) for x in self),
            self.query_id,
            self.cache_time,
            self.users,
            self.gallery,
            self.next_offset,
            self.switch_pm
        ))

    def __str__(self):
        return self._to_str(str)

    def __repr__(self):
        return self._to_str(repr)
