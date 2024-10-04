from __future__ import annotations

import itertools
import sys
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Sequence

from ....tl import abcs, types
from .channel import Channel
from .group import Group
from .peer import Peer
from .user import User

if TYPE_CHECKING:
    from ...client.client import Client


def build_chat_map(client: Client, users: Sequence[abcs.User], chats: Sequence[abcs.Chat]) -> dict[int, Peer]:
    users_iter = (User._from_raw(u) for u in users)
    chats_iter = (
        (
            Channel._from_raw(c)
            if isinstance(c, (types.Channel, types.ChannelForbidden)) and c.broadcast
            else Group._from_raw(client, c)
        )
        for c in chats
    )

    result: dict[int, Peer] = {c.id: c for c in itertools.chain(users_iter, chats_iter)}

    if len(result) != len(users) + len(chats):
        # The fabled ID collision between different chat types.
        counter: defaultdict[int, list[abcs.User | abcs.Chat]] = defaultdict(list)
        for user in users:
            if (id := getattr(user, "id", None)) is not None:
                counter[id].append(user)
        for chat in chats:
            if (id := getattr(chat, "id", None)) is not None:
                counter[id].append(chat)

        for k, v in counter.items():
            if len(v) > 1:
                for x in v:
                    print(x, file=sys.stderr)

                raise RuntimeError(f"chat identifier collision: {k}; please report this")

    return result


def peer_id(peer: abcs.Peer) -> int:
    if isinstance(peer, types.PeerUser):
        return peer.user_id
    elif isinstance(peer, types.PeerChat):
        return peer.chat_id
    elif isinstance(peer, types.PeerChannel):
        return peer.channel_id
    else:
        raise RuntimeError("unexpected case")


def expand_peer(client: Client, peer: abcs.Peer, *, broadcast: Optional[bool]) -> Peer:
    if isinstance(peer, types.PeerUser):
        return User._from_raw(types.UserEmpty(id=peer.user_id))
    elif isinstance(peer, types.PeerChat):
        return Group._from_raw(client, types.ChatEmpty(id=peer.chat_id))
    elif isinstance(peer, types.PeerChannel):
        if broadcast is None:
            broadcast = True  # assume broadcast by default (Channel type is more accurate than Group)

        channel = types.ChannelForbidden(
            broadcast=broadcast,
            megagroup=not broadcast,
            id=peer.channel_id,
            access_hash=0,
            title="",
            until_date=None,
        )

        return Channel._from_raw(channel) if broadcast else Group._from_raw(client, channel)
    else:
        raise RuntimeError("unexpected case")


__all__ = ["Channel", "Peer", "Group", "User"]
