from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...mtproto import RpcError
from ...session import PackedChat, PackedType
from ...tl import abcs, functions, types
from ..types import AsyncList, Channel, Chat, ChatLike, Group, User
from ..utils import build_chat_map, peer_id

if TYPE_CHECKING:
    from .client import Client


async def get_me(self: Client) -> Optional[User]:
    try:
        result = await self(functions.users.get_users(id=[types.InputUserSelf()]))
    except RpcError as e:
        if e.code == 401:
            return None
        else:
            raise

    assert len(result) == 1
    return User._from_raw(result[0])


class ContactList(AsyncList[User]):
    def __init__(self, client: Client):
        super().__init__()
        self._client = client

    async def _fetch_next(self) -> None:
        result = await self._client(functions.contacts.get_contacts(hash=0))
        assert isinstance(result, types.contacts.Contacts)

        self._buffer.extend(User._from_raw(u) for u in result.users)
        self._total = len(self._buffer)
        self._done = True


def get_contacts(self: Client) -> AsyncList[User]:
    return ContactList(self)


def resolved_peer_to_chat(resolved: abcs.contacts.ResolvedPeer) -> Chat:
    assert isinstance(resolved, types.contacts.ResolvedPeer)

    map = build_chat_map(resolved.users, resolved.chats)
    if chat := map.get(peer_id(resolved.peer)):
        return chat
    else:
        raise ValueError(f"no matching chat found in response")


async def resolve_phone(client: Client, phone: str) -> Chat:
    return resolved_peer_to_chat(
        await client(functions.contacts.resolve_phone(phone=phone))
    )


async def resolve_username(self: Client, username: str) -> Chat:
    return resolved_peer_to_chat(
        await self(functions.contacts.resolve_username(username=username))
    )


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
                id=self._chat_hashes.self_id,
                access_hash=0,  # TODO get hash
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

    if isinstance(chat, str):
        if chat.startswith("+"):
            resolved = await resolve_phone(self, chat)
        elif chat == "me":
            if me := self._config.session.user:
                return PackedChat(
                    ty=PackedType.BOT if me.bot else PackedType.USER,
                    id=me.id,
                    access_hash=0,
                )
            else:
                resolved = None
        else:
            resolved = await resolve_username(self, username=chat)

        if resolved and (packed := resolved.pack()) is not None:
            return packed

    raise ValueError("Cannot resolve chat")


def input_to_peer(
    client: Client, input: Optional[abcs.InputPeer]
) -> Optional[abcs.Peer]:
    if input is None:
        return None
    elif isinstance(input, types.InputPeerEmpty):
        return None
    elif isinstance(input, types.InputPeerSelf):
        return types.PeerUser(user_id=client._chat_hashes.self_id)
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
