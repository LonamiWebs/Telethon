import inspect
import itertools
from dataclasses import dataclass, field
from collections import namedtuple

from .._misc import utils
from .. import _tl
from .._sessions.types import EntityType, Entity


class PackedChat(namedtuple('PackedChat', 'ty id hash')):
    __slots__ = ()

    @property
    def is_user(self):
        return self.ty in (EntityType.USER, EntityType.BOT)

    @property
    def is_chat(self):
        return self.ty in (EntityType.GROUP,)

    @property
    def is_channel(self):
        return self.ty in (EntityType.CHANNEL, EntityType.MEGAGROUP, EntityType.GIGAGROUP)

    def to_peer(self):
        if self.is_user:
            return _tl.PeerUser(user_id=self.id)
        elif self.is_chat:
            return _tl.PeerChat(chat_id=self.id)
        elif self.is_channel:
            return _tl.PeerChannel(channel_id=self.id)

    def to_input_peer(self):
        if self.is_user:
            return _tl.InputPeerUser(user_id=self.id, access_hash=self.hash)
        elif self.is_chat:
            return _tl.InputPeerChat(chat_id=self.id)
        elif self.is_channel:
            return _tl.InputPeerChannel(channel_id=self.id, access_hash=self.hash)

    def try_to_input_user(self):
        if self.is_user:
            return _tl.InputUser(user_id=self.id, access_hash=self.hash)
        else:
            return None

    def try_to_chat_id(self):
        if self.is_chat:
            return self.id
        else:
            return None

    def try_to_input_channel(self):
        if self.is_channel:
            return _tl.InputChannel(channel_id=self.id, access_hash=self.hash)
        else:
            return None

    def __str__(self):
        return f'{chr(self.ty.value)}.{self.id}.{self.hash}'


@dataclass
class EntityCache:
    hash_map: dict = field(default_factory=dict)  # id -> (hash, ty)
    self_id: int = None
    self_bot: bool = False

    def set_self_user(self, id, bot):
        self.self_id = id
        self.self_bot = bot

    def get(self, id):
        value = self.hash_map.get(id)
        return PackedChat(ty=value[1], id=id, hash=value[0]) if value else None

    def extend(self, users, chats):
        # See https://core.telegram.org/api/min for "issues" with "min constructors".
        self.hash_map.update(
            (u.id, (
                u.access_hash,
                EntityType.BOT if u.bot else EntityType.USER,
            ))
            for u in users
            if getattr(u, 'access_hash', None) and not u.min
        )
        self.hash_map.update(
            (c.id, (
                c.access_hash,
                EntityType.MEGAGROUP if c.megagroup else (
                    EntityType.GIGAGROUP if getattr(c, 'gigagroup', None) else EntityType.CHANNEL
                ),
            ))
            for c in chats
            if getattr(c, 'access_hash', None) and not getattr(c, 'min', None)
        )

    def get_all_entities(self):
        return [Entity(ty, id, hash) for id, (hash, ty) in self.hash_map.items()]

    def put(self, entity):
        self.hash_map[entity.id] = (entity.access_hash, entity.ty)
