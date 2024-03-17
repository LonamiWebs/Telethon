from ...tl import abcs, types
from .meta import NoPublicConstructor
from .peer import Peer


class RecentAction(metaclass=NoPublicConstructor):
    """
    A recent action in a chat, also known as an "admin log event action" or :tl:`ChannelAdminLogEvent`.

    Only administrators of the chat can access these.

    You can obtain recent actions with methods such as :meth:`telethon.Client.get_admin_log`.
    """

    def __init__(
        self,
        event: abcs.ChannelAdminLogEvent,
        chat_map: dict[int, Peer],
    ) -> None:
        assert isinstance(event, types.ChannelAdminLogEvent)
        self._raw = event
        self._chat_map = chat_map

    @property
    def id(self) -> int:
        """
        The identifier of this action.

        This identifier is *not* the same as the one in the message that was edited or deleted.
        """
        return self._raw.id
