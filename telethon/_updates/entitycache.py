import inspect
import itertools
from dataclasses import dataclass, field
from collections import namedtuple

from .._misc import utils
from .. import _tl
from .._sessions.types import EntityType, Entity


@dataclass
class EntityCache:
    hash_map: dict = field(default_factory=dict)  # id -> (hash, ty)
    self_id: int = None
    self_bot: bool = False

    def set_self_user(self, id, bot):
        self.self_id = id
        self.self_bot = bot

    def get(self, id):
        try:
            hash, ty = self.hash_map[id]
            return Entity(ty, id, hash)
        except KeyError:
            return None

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
        self.hash_map[entity.id] = (entity.hash, entity.ty)
