import re
from typing import Union

from ..event import Event


class Text:
    """
    Filter by ``event.text`` using a *regular expression* pattern.

    The pattern is searched on the text anywhere, not matched at the start.
    Use the ``'^'`` anchor if you want to match the text from the start.

    The match, if any, is discarded. If you need to access captured groups,
    you need to manually perform the check inside the handler instead.
    """

    __slots__ = ("_pattern",)

    def __init__(self, regexp: Union[str, re.Pattern[str]]) -> None:
        self._pattern = re.compile(regexp) if isinstance(regexp, str) else regexp

    def __call__(self, event: Event) -> bool:
        text = getattr(event, "text", None)
        return re.search(self._pattern, text) is not None if text is not None else False


class Command:
    """
    Filter by ``event.text`` to make sure the first word matches the command or
    the command + '@' + username, using the username of the logged-in account.

    For example, if the logged-in account has an username of "bot", then the
    filter ``Command('/help')`` will match both ``"/help"`` and ``"/help@bot"``, but not
    ``"/list"`` or ``"/help@other"``.

    Note that the leading forward-slash is not automatically added,
    which allows for using a different prefix or no prefix at all.
    """

    __slots__ = ("_cmd",)

    def __init__(self, command: str) -> None:
        self._cmd = command

    def __call__(self, event: Event) -> bool:
        raise NotImplementedError


class Incoming:
    """
    Filter by ``event.incoming``, that is, messages sent from others to the
    logged-in account.

    This is not a reliable way to check that the update was not produced by
    the logged-in account in broadcast channels.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "incoming", False)


class Outgoing:
    """
    Filter by ``event.outgoing``, that is, messages sent from others to the
    logged-in account.

    This is not a reliable way to check that the update was not produced by
    the logged-in account in broadcast channels.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "outgoing", False)


class Forward:
    """
    Filter by ``event.forward``.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "forward", None) is not None


class Reply:
    """
    Filter by ``event.reply``.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "reply", None) is not None
