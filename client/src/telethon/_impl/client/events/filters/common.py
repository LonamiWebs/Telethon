from typing import Sequence, Set, Type, Union

from ...types import Channel, Group, User
from ..event import Event
from .combinators import Combinable


class Chats(Combinable):
    """
    Filter by ``event.chat.id``, if the event has a chat.

    :param chat_ids: The chat identifiers to filter on.
    """

    __slots__ = ("_chats",)

    def __init__(self, chat_ids: Sequence[int]) -> None:
        self._chats = set(chat_ids)

    @property
    def chat_ids(self) -> Set[int]:
        """
        A copy of the set of chat identifiers this filter is filtering on.
        """
        return set(self._chats)

    def __call__(self, event: Event) -> bool:
        chat = getattr(event, "chat", None)
        id = getattr(chat, "id", None)
        return id in self._chats


class Senders(Combinable):
    """
    Filter by ``event.sender.id``, if the event has a sender.

    :param sender_ids: The sender identifiers to filter on.
    """

    __slots__ = ("_senders",)

    def __init__(self, sender_ids: Sequence[int]) -> None:
        self._senders = set(sender_ids)

    @property
    def sender_ids(self) -> Set[int]:
        """
        A copy of the set of sender identifiers this filter is filtering on.
        """
        return set(self._senders)

    def __call__(self, event: Event) -> bool:
        sender = getattr(event, "sender", None)
        id = getattr(sender, "id", None)
        return id in self._senders


class ChatType(Combinable):
    """
    Filter by chat type using :func:`isinstance`.

    :param type: The chat type to filter on.

    .. rubric:: Example

    .. code-block:: python

        from telethon import events
        from telethon.events import filters
        from telethon.types import Channel

        # Handle only messages from broadcast channels
        @client.on(events.NewMessage, filters.ChatType(Channel))
        async def handler(event):
            print(event.text)
    """

    __slots__ = ("_type",)

    def __init__(
        self,
        type: Type[Union[User, Group, Channel]],
    ) -> None:
        self._type = type

    @property
    def type(self) -> Type[Union[User, Group, Channel]]:
        """
        The chat type this filter is filtering on.
        """
        return self._type

    def __call__(self, event: Event) -> bool:
        sender = getattr(event, "chat", None)
        return isinstance(sender, self._type)
