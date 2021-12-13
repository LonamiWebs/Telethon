from .types import DataCenter, ChannelState, SessionState, Entity, get_entity_type_group
from .abstract import Session
from .._misc import utils, tlobject
from .. import _tl

from typing import List, Optional


class MemorySession(Session):
    __slots__ = ('dcs', 'state', 'channel_states', 'entities')

    def __init__(self):
        self.dcs = {}
        self.state = None
        self.channel_states = {}
        self.entities = {}

    async def insert_dc(self, dc: DataCenter):
        self.dcs[dc.id] = dc

    async def get_all_dc(self) -> List[DataCenter]:
        return list(self.dcs.values())

    async def set_state(self, state: SessionState):
        self.state = state

    async def get_state(self) -> Optional[SessionState]:
        return self.state

    async def insert_channel_state(self, state: ChannelState):
        self.channel_states[state.channel_id] = state

    async def get_all_channel_states(self) -> List[ChannelState]:
        return list(self.channel_states.values())

    async def insert_entities(self, entities: List[Entity]):
        self.entities.update(((get_peer_canonical_entity_type(e.ty), e.id), e.access_hash) for e in entities)

    async def get_entity(self, ty: int, id: int) -> Optional[Entity]:
        try:
            access_hash = self.entities[get_peer_canonical_entity_type(ty), id]
            return Entity(ty, id, access_hash)
        except KeyError:
            return None

    async def save(self):
        pass
