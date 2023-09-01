from typing import Union

from ....session.chat.packed import PackedChat
from .channel import Channel
from .group import Group
from .user import RestrictionReason, User

Chat = Union[Channel, Group, User]
ChatLike = Union[Chat, PackedChat, int, str]

__all__ = ["Chat", "Channel", "Group", "RestrictionReason", "User"]
