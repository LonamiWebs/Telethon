from typing import Optional, Self

from ....session import ChannelRef
from ....tl import abcs, types
from ..meta import NoPublicConstructor
from .peer import Peer


class Channel(Peer, metaclass=NoPublicConstructor):
    """
    A broadcast channel.

    You can get a channel from messages via :attr:`telethon.types.Message.chat`,
    or from methods such as :meth:`telethon.Client.resolve_username`.
    """

    def __init__(
        self,
        raw: types.Channel | types.ChannelForbidden,
    ) -> None:
        self._raw = raw

    @classmethod
    def _from_raw(cls, chat: abcs.Chat) -> Self:
        if isinstance(chat, (types.ChatEmpty, types.Chat, types.ChatForbidden)):
            raise RuntimeError("cannot create channel from group chat")
        elif isinstance(chat, (types.Channel, types.ChannelForbidden)):
            if not chat.broadcast:
                raise RuntimeError("cannot create group from broadcast channel")
            return cls._create(chat)
        else:
            raise RuntimeError("unexpected case")

    # region Overrides

    @property
    def id(self) -> int:
        return self._raw.id

    @property
    def name(self) -> str:
        """
        The channel's title.

        This property is always present, but may be the empty string.
        """
        return self._raw.title

    @property
    def username(self) -> Optional[str]:
        return getattr(self._raw, "username", None)

    @property
    def ref(self) -> ChannelRef:
        return ChannelRef(self._raw.id, self._raw.access_hash)

    @property
    def _ref(self) -> ChannelRef:
        return self.ref

    # endregion Overrides
