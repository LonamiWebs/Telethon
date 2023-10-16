from typing import Optional, Self, Union

from ....session import PackedChat, PackedType
from ....tl import abcs, types
from ..meta import NoPublicConstructor
from .chat import Chat


class Group(Chat, metaclass=NoPublicConstructor):
    """
    A small group or supergroup.

    You can get a group from messages via :attr:`telethon.types.Message.chat`,
    or from methods such as :meth:`telethon.Client.resolve_username`.
    """

    __slots__ = ("_raw",)

    def __init__(
        self,
        raw: Union[
            types.ChatEmpty,
            types.Chat,
            types.ChatForbidden,
            types.Channel,
            types.ChannelForbidden,
        ],
    ) -> None:
        self._raw = raw

    @classmethod
    def _from_raw(cls, chat: abcs.Chat) -> Self:
        if isinstance(chat, (types.ChatEmpty, types.Chat, types.ChatForbidden)):
            return cls._create(chat)
        elif isinstance(chat, (types.Channel, types.ChannelForbidden)):
            if chat.broadcast:
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
        The group's title.

        This property is always present, but may be the empty string.
        """
        return self._raw.title

    @property
    def username(self) -> Optional[str]:
        return getattr(self._raw, "username", None)

    def pack(self) -> Optional[PackedChat]:
        if isinstance(self._raw, (types.ChatEmpty, types.Chat, types.ChatForbidden)):
            return PackedChat(ty=PackedType.CHAT, id=self._raw.id, access_hash=None)
        elif self._raw.access_hash is None:
            return None
        else:
            return PackedChat(
                ty=PackedType.MEGAGROUP, id=self._raw.id, access_hash=None
            )

    # endregion Overrides

    @property
    def is_megagroup(self) -> bool:
        """
        Whether the group is a supergroup.

        These are known as "megagroups" in Telegram's API, and are different from "gigagroups".
        """
        return isinstance(self._raw, (types.Channel, types.ChannelForbidden))
