from typing import Optional, Self, Union

from ....session.chat.packed import PackedChat, PackedType
from ....tl import abcs, types
from ..meta import NoPublicConstructor


class Channel(metaclass=NoPublicConstructor):
    __slots__ = ("_raw",)

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

    @property
    def id(self) -> int:
        return self._raw.id

    def pack(self) -> Optional[PackedChat]:
        if self._raw.access_hash is None:
            return None
        else:
            return PackedChat(
                ty=PackedType.GIGAGROUP
                if getattr(self._raw, "gigagroup", False)
                else PackedType.BROADCAST,
                id=self._raw.id,
                access_hash=None,
            )

    @property
    def title(self) -> str:
        return getattr(self._raw, "title", None) or ""

    @property
    def username(self) -> Optional[str]:
        return getattr(self._raw, "username", None)
