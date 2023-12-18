from typing import Optional, Self, Union

from ....session import PackedChat, PackedType
from ....tl import abcs, types
from ..meta import NoPublicConstructor
from .chat import Chat


class Channel(Chat, metaclass=NoPublicConstructor):
    """
    A broadcast channel.

    You can get a channel from messages via :attr:`telethon.types.Message.chat`,
    or from methods such as :meth:`telethon.Client.resolve_username`.
    """

    def __init__(
        self,
        raw: Union[types.Channel, types.ChannelForbidden],
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

    def pack(self) -> Optional[PackedChat]:
        if self._raw.access_hash is None:
            return None
        else:
            if getattr(self._raw, "megagroup", False):
                ty = PackedType.MEGAGROUP
            elif getattr(self._raw, "gigagroup", False):
                ty = PackedType.GIGAGROUP
            else:
                ty = PackedType.BROADCAST
            return PackedChat(
                ty=ty,
                id=self._raw.id,
                access_hash=self._raw.access_hash,
            )

    # endregion Overrides
