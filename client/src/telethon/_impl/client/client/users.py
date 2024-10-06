from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

from ...mtproto import RpcError
from ...session import GroupRef, PeerRef, UserRef
from ...tl import abcs, functions, types
from ..types import AsyncList, Peer, User, build_chat_map, expand_peer, peer_id

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


def resolved_peer_to_chat(client: Client, resolved: abcs.contacts.ResolvedPeer) -> Peer:
    assert isinstance(resolved, types.contacts.ResolvedPeer)

    map = build_chat_map(client, resolved.users, resolved.chats)
    if chat := map.get(peer_id(resolved.peer)):
        return chat
    else:
        raise ValueError("no matching chat found in response")


async def resolve_phone(self: Client, phone: str, /) -> Peer:
    return resolved_peer_to_chat(
        self, await self(functions.contacts.resolve_phone(phone=phone))
    )


async def resolve_username(self: Client, username: str, /) -> Peer:
    return resolved_peer_to_chat(
        self, await self(functions.contacts.resolve_username(username=username))
    )


async def resolve_peers(self: Client, peers: Sequence[Peer | PeerRef], /) -> list[Peer]:
    refs: list[PeerRef] = []
    input_users: list[abcs.InputUser] = []
    input_chats: list[int] = []
    input_channels: list[abcs.InputChannel] = []

    for peer in peers:
        peer = peer._ref
        refs.append(peer)
        if isinstance(peer, UserRef):
            input_users.append(peer._to_input_user())
        elif isinstance(peer, GroupRef):
            input_chats.append(peer._to_input_chat())
        else:
            input_channels.append(peer._to_input_channel())

    if input_users:
        ret_users = await self(functions.users.get_users(id=input_users))
        users = list(ret_users)
    else:
        users = []

    if input_chats:
        ret_chats = await self(functions.messages.get_chats(id=input_chats))
        assert isinstance(ret_chats, types.messages.Chats)
        chats = list(ret_chats.chats)
    else:
        chats = []

    if input_channels:
        ret_chats = await self(functions.channels.get_channels(id=input_channels))
        assert isinstance(ret_chats, types.messages.Chats)
        chats.extend(ret_chats.chats)

    chat_map = build_chat_map(self, users, chats)
    return [
        chat_map.get(ref.identifier)
        or expand_peer(self, ref._to_peer(), broadcast=None)
        for ref in refs
    ]
