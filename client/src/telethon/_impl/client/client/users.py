from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...session.chat.packed import PackedChat, PackedType
from ...tl import abcs, types
from ..types.chat import Channel, ChatLike, Group, User

if TYPE_CHECKING:
    from .client import Client


async def get_me(self: Client) -> None:
    self
    raise NotImplementedError


async def is_bot(self: Client) -> None:
    self
    raise NotImplementedError


async def is_user_authorized(self: Client) -> None:
    self
    raise NotImplementedError


async def get_entity(self: Client) -> None:
    self
    raise NotImplementedError


async def get_input_entity(self: Client) -> None:
    self
    raise NotImplementedError


async def get_peer_id(self: Client) -> None:
    self
    raise NotImplementedError


async def resolve_to_packed(self: Client, chat: ChatLike) -> PackedChat:
    if isinstance(chat, (User, Group, Channel)):
        packed = chat.pack()
        if packed is None:
            raise ValueError("Cannot resolve chat")
        return packed

    if isinstance(chat, abcs.InputPeer):
        if isinstance(chat, types.InputPeerEmpty):
            raise ValueError("Cannot resolve chat")
        elif isinstance(chat, types.InputPeerSelf):
            if not self._config.session.user:
                raise ValueError("Cannot resolve chat")
            return PackedChat(
                ty=PackedType.BOT if self._config.session.user.bot else PackedType.USER,
                id=self._config.session.user.id,
                access_hash=0,
            )
        elif isinstance(chat, types.InputPeerChat):
            return PackedChat(
                ty=PackedType.CHAT,
                id=chat.chat_id,
                access_hash=None,
            )
        elif isinstance(chat, types.InputPeerUser):
            return PackedChat(
                ty=PackedType.USER,
                id=chat.user_id,
                access_hash=chat.access_hash,
            )
        elif isinstance(chat, types.InputPeerChannel):
            return PackedChat(
                ty=PackedType.BROADCAST,
                id=chat.channel_id,
                access_hash=chat.access_hash,
            )
        elif isinstance(chat, types.InputPeerUserFromMessage):
            raise ValueError("Cannot resolve chat")
        elif isinstance(chat, types.InputPeerChannelFromMessage):
            raise ValueError("Cannot resolve chat")
        else:
            raise RuntimeError("unexpected case")

    raise ValueError("Cannot resolve chat")


def input_as_peer(self: Client, input: Optional[abcs.InputPeer]) -> Optional[abcs.Peer]:
    if input is None:
        return None
    elif isinstance(input, types.InputPeerEmpty):
        return None
    elif isinstance(input, types.InputPeerSelf):
        return (
            types.PeerUser(user_id=self._config.session.user.id)
            if self._config.session.user
            else None
        )
    elif isinstance(input, types.InputPeerChat):
        return types.PeerChat(chat_id=input.chat_id)
    elif isinstance(input, types.InputPeerUser):
        return types.PeerUser(user_id=input.user_id)
    elif isinstance(input, types.InputPeerChannel):
        return types.PeerChannel(channel_id=input.channel_id)
    elif isinstance(input, types.InputPeerUserFromMessage):
        return None
    elif isinstance(input, types.InputPeerChannelFromMessage):
        return None
    else:
        raise RuntimeError("unexpected case")
