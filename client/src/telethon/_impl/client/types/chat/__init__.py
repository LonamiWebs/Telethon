from typing import Union

from ....session import PackedChat
from .channel import Channel
from .chat import Chat
from .group import Group
from .user import User

ChatLike = Union[Chat, PackedChat, int, str]

__all__ = ["Chat", "ChatLike", "Channel", "Group", "User"]
