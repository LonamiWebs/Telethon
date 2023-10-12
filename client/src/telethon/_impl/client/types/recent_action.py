from typing import Dict

from ...tl import abcs, types
from .chat import Chat
from .meta import NoPublicConstructor


class RecentAction(metaclass=NoPublicConstructor):
    """
    A recent action in a chat, also known as an "admin log event action" or :tl:`ChannelAdminLogEvent`.

    Only administrators of the chat can access these.

    You can obtain recent actions with methods such as :meth:`telethon.Client.get_admin_log`.
    """

    __slots__ = ("_raw", "_chat_map")

    def __init__(
        self,
        event: abcs.ChannelAdminLogEvent,
        chat_map: Dict[int, Chat],
    ) -> None:
        assert isinstance(event, types.ChannelAdminLogEvent)
        self._raw = event
        self._chat_map = chat_map

    @property
    def id(self) -> int:
        return self._raw.id
