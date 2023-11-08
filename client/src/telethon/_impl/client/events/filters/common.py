from typing import Literal, Sequence, Tuple, Type, Union

from ...types import Channel, Group, User
from ..event import Event
from .combinators import Combinable


class Chats(Combinable):
    """
    Filter by ``event.chat.id``, if the event has a chat.
    """

    __slots__ = ("_chats",)

    def __init__(self, chat_id: Union[int, Sequence[int]], *chat_ids: int) -> None:
        self._chats = {chat_id} if isinstance(chat_id, int) else set(chat_id)
        self._chats.update(chat_ids)

    @property
    def chat_ids(self) -> Tuple[int, ...]:
        """
        The chat identifiers this filter is filtering on.
        """
        return tuple(self._chats)

    def __call__(self, event: Event) -> bool:
        chat = getattr(event, "chat", None)
        id = getattr(chat, "id", None)
        return id in self._chats


class Senders(Combinable):
    """
    Filter by ``event.sender.id``, if the event has a sender.
    """

    __slots__ = ("_senders",)

    def __init__(self, sender_id: Union[int, Sequence[int]], *sender_ids: int) -> None:
        self._senders = {sender_id} if isinstance(sender_id, int) else set(sender_id)
        self._senders.update(sender_ids)

    @property
    def sender_ids(self) -> Tuple[int, ...]:
        """
        The sender identifiers this filter is filtering on.
        """
        return tuple(self._senders)

    def __call__(self, event: Event) -> bool:
        sender = getattr(event, "sender", None)
        id = getattr(sender, "id", None)
        return id in self._senders


class ChatType(Combinable):
    """
    Filter by chat type, either ``'user'``, ``'group'`` or ``'broadcast'``.
    """

    __slots__ = ("_type",)

    def __init__(
        self,
        type: Union[Literal["user"], Literal["group"], Literal["broadcast"]],
    ) -> None:
        if type == "user":
            self._type: Union[Type[User], Type[Group], Type[Channel]] = User
        elif type == "group":
            self._type = Group
        elif type == "broadcast":
            self._type = Channel
        else:
            raise TypeError(f"unrecognised chat type: {type}")

    @property
    def type(self) -> Union[Literal["user"], Literal["group"], Literal["broadcast"]]:
        """
        The chat type this filter is filtering on.
        """
        if self._type == User:
            return "user"
        elif self._type == Group:
            return "group"
        elif self._type == Channel:
            return "broadcast"
        else:
            raise RuntimeError("unexpected case")

    def __call__(self, event: Event) -> bool:
        chat = getattr(event, "chat", None)
        return isinstance(chat, self._type)
