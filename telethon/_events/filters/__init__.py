from .base import Filter, And, Or, Not, Identity, Always, Never
from .generic import Types
from .entities import Chats, Senders
from .messages import Incoming, Outgoing, Pattern, Data


_sentinel = object()


def make_filter(
        chats=_sentinel,
        blacklist_chats=_sentinel,
        func=_sentinel,
        types=_sentinel,
        incoming=_sentinel,
        outgoing=_sentinel,
        senders=_sentinel,
        blacklist_senders=_sentinel,
        forwards=_sentinel,
        pattern=_sentinel,
        data=_sentinel,
):
    """
    Create a new `And` filter joining all the filters specified as input parameters.

    Not all filters may have an effect on all events.

    chats (`entity`, optional):
        May be one or more entities (username/peer/etc.), preferably IDs.
        By default, only matching chats will be handled.

    blacklist_chats (`bool`, optional):
        Whether to treat the chats as a blacklist instead of
        as a whitelist (default). This means that every chat
        will be handled *except* those specified in ``chats``
        which will be ignored if ``blacklist_chats=True``.

    func (`callable`, optional):
        A callable (async or not) function that should accept the event as input
        parameter, and return a value indicating whether the event
        should be dispatched or not (any truthy value will do, it
        does not need to be a `bool`). It works like a custom filter:

        .. code-block:: python

            @client.on(events.NewMessage(func=lambda e: e.is_private))
            async def handler(event):
                pass  # code here

    incoming (`bool`, optional):
        If set to `True`, only **incoming** messages will be handled.
        If set to `False`, incoming messages will be ignored.
        If both incoming are outgoing are set, whichever is true will be handled.

    outgoing (`bool`, optional):
        If set to `True`, only **outgoing** messages will be handled.
        If set to `False`, outgoing messages will be ignored.
        If both incoming are outgoing are set, whichever is true will be handled.

    senders (`entity`, optional):
        Unlike `chats`, this parameter filters the *senders* of the
        message. That is, only messages *sent by these users* will be
        handled. Use `chats` if you want private messages with this/these
        users. `senders` lets you filter by messages sent by *one or
        more* users across the desired chats (doesn't need a list).

    blacklist_senders (`bool`):
        Whether to treat the senders as a blacklist instead of
        as a whitelist (default). This means that every sender
        will be handled *except* those specified in ``senders``
        which will be ignored if ``blacklist_senders=True``.

    forwards (`bool`, optional):
        Whether forwarded messages should be handled or not. By default,
        both forwarded and normal messages are included. If it's `True`
        *only* forwards will be handled. If it's `False` only messages
        that are *not* forwards will be handled.

    pattern (`str`, `callable`, `Pattern`, optional):
        If set, only messages matching this pattern will be handled.
        You can specify a regex-like string which will be matched
        against the message, a callable function that returns `True`
        if a message is acceptable, or a compiled regex pattern.

    data (`bytes`, `str`, `callable`, optional):
        If set, the inline button payload data must match this data.
        A UTF-8 string can also be given, a regex or a callable. For
        instance, to check against ``'data_1'`` and ``'data_2'`` you
        can use ``re.compile(b'data_')``.

    types (`list` | `tuple` | `type`, optional):
        The type or types that the :tl:`Update` instance must be.
        Equivalent to ``if not isinstance(update, types): return``.
    """
    filters = []

    if chats is not _sentinel:
        f = Chats(chats)
        if blacklist_chats is not _sentinel and blacklist_chats:
            f = Not(f)
        filters.append(f)

    if func is not _sentinel:
        filters.append(Identity(func))

    if types is not _sentinel:
        filters.append(Types(types))

    if incoming is not _sentinel:
        if outgoing is not _sentinel:
            if incoming and outgoing:
                pass  # no need to filter
            elif incoming:
                filters.append(Incoming())
            elif outgoing:
                filters.append(Outgoing())
            else:
                return Never()  # why?
        elif incoming:
            filters.append(Incoming())
        else:
            filters.append(Outgoing())
    elif outgoing is not _sentinel:
        if outgoing:
            filters.append(Outgoing())
        else:
            filters.append(Incoming())

    if senders is not _sentinel:
        f = Senders(senders)
        if blacklist_senders is not _sentinel and blacklist_senders:
            f = Not(f)
        filters.append(f)

    if forwards is not _sentinel:
        filters.append(Forward())

    if pattern is not _sentinel:
        filters.append(Pattern(pattern))

    if data is not _sentinel:
        filters.append(Data(data))

    return And(*filters) if filters else Always()


class NotResolved(ValueError):
    def __init__(self, unresolved):
        super().__init__()
        self.unresolved = unresolved
