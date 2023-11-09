from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal, Optional, Tuple, Union

from ..event import Event
from .combinators import Combinable

if TYPE_CHECKING:
    from ...client.client import Client


class Text(Combinable):
    """
    Filter by ``event.text`` using a *regular expression* pattern.

    The pattern is searched on the text anywhere, not matched at the start.
    Use the ``'^'`` anchor if you want to match the text from the start.

    The match, if any, is discarded. If you need to access captured groups,
    you need to manually perform the check inside the handler instead.

    Note that the caption text in messages with media is also searched.
    If you want to filter based on media, use :class:`Media`.

    :param regexp: The regular expression to :func:`re.search` with on the text.
    """

    __slots__ = ("_pattern",)

    def __init__(self, regexp: Union[str, re.Pattern[str]]) -> None:
        self._pattern = re.compile(regexp) if isinstance(regexp, str) else regexp

    def __call__(self, event: Event) -> bool:
        text = getattr(event, "text", None)
        return re.search(self._pattern, text) is not None if text is not None else False


class Command(Combinable):
    """
    Filter by ``event.text`` to make sure the first word matches the command or
    the command + '@' + username, using the username of the logged-in account.

    For example, if the logged-in account has an username of "bot", then the
    filter ``Command('/help')`` will match both ``"/help"`` and ``"/help@bot"``, but not
    ``"/list"`` or ``"/help@other"``.

    :param command: The command to match on.

    .. note::

        The leading forward-slash is not automatically added!
        This allows for using a different prefix or no prefix at all.

    .. note::

        The username is taken from the :term:`session` to avoid network calls.
        If a custom storage returns the incorrect username, the filter will misbehave.
        If there is no username, then the ``"/help@other"`` syntax will be ignored.
    """

    __slots__ = ("_cmd", "_username")

    def __init__(self, command: str) -> None:
        if re.search(r"\s", command):
            raise ValueError(f"command cannot contain spaces: {command}")

        self._cmd = command
        self._username: Optional[str] = None

    def __call__(self, event: Event) -> bool:
        text: Optional[str] = getattr(event, "text", None)
        if not text:
            return False

        if self._username is None:
            self._username = ""
            client: Optional[Client]
            if (client := getattr(event, "_client", None)) is not None:
                user = client._session.user
                if user and user.username:
                    self._username = user.username

        cmd = text.split(maxsplit=1)[0]
        if cmd == self._cmd:
            return True
        if self._username:
            return cmd == f"{self._cmd}@{self._username}"
        return False


class Incoming(Combinable):
    """
    Filter by ``event.incoming``, that is, messages sent from others to the logged-in account.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "incoming", False)


class Outgoing(Combinable):
    """
    Filter by ``event.outgoing``, that is, messages sent from the logged-in account.

    This is not a reliable way to check that the update was not produced by the logged-in account in broadcast channels.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "outgoing", False)


class Forward(Combinable):
    """
    Filter by ``event.forward_info``, that is, messages that have been forwarded from elsewhere.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "forward_info", None) is not None


class Reply(Combinable):
    """
    Filter by ``event.replied_message_id``, that is, messages which are a reply to another message.
    """

    __slots__ = ()

    def __call__(self, event: Event) -> bool:
        return getattr(event, "replied_message_id", None) is not None


class Media(Combinable):
    """
    Filter by the media type in the message.

    By default, this filter will pass if the message has any media.

    Note that link previews are only considered media if they have a photo or document.

    When you specify one or more media types, *only* those types will be considered.

    You can use literal strings or the constants defined by the filter.

    :param types:
        The media types to filter on.
        This is all of them if none are specified.
    """

    PHOTO = "photo"
    AUDIO = "audio"
    VIDEO = "video"

    __slots__ = "_types"

    def __init__(
        self, *types: Union[Literal["photo"], Literal["audio"], Literal["video"]]
    ) -> None:
        self._types = types or None

    @property
    def types(
        self,
    ) -> Tuple[Union[Literal["photo"], Literal["audio"], Literal["video"]], ...]:
        """
        The media types being checked.
        """
        return self._types or ()

    def __call__(self, event: Event) -> bool:
        if self._types is None:
            return getattr(event, "file", None) is not None
        else:
            return any(getattr(event, ty, None) is not None for ty in self._types)
