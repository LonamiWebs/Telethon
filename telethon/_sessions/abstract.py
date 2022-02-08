from .types import DataCenter, ChannelState, SessionState, EntityType, Entity

from abc import ABC, abstractmethod
from typing import List, Optional


class Session(ABC):
    @abstractmethod
    async def insert_dc(self, dc: DataCenter):
        """
        Store a new or update an existing `DataCenter` with matching ``id``.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all_dc(self) -> List[DataCenter]:
        """
        Get a list of all currently-stored `DataCenter`. Should not contain duplicate ``id``.
        """
        raise NotImplementedError

    @abstractmethod
    async def set_state(self, state: SessionState):
        """
        Set the state about the current session.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_state(self) -> Optional[SessionState]:
        """
        Get the state about the current session.
        """
        raise NotImplementedError

    @abstractmethod
    async def insert_channel_state(self, state: ChannelState):
        """
        Store a new or update an existing `ChannelState` with matching ``id``.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all_channel_states(self) -> List[ChannelState]:
        """
        Get a list of all currently-stored `ChannelState`. Should not contain duplicate ``id``.
        """
        raise NotImplementedError

    @abstractmethod
    async def insert_entities(self, entities: List[Entity]):
        """
        Store new or update existing `Entity` with matching ``id``.

        Entities should be saved on a best-effort. It is okay to not save them, although the
        library may need to do extra work if a previously-saved entity is missing, or even be
        unable to continue without the entity.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_entity(self, ty: Optional[EntityType], id: int) -> Optional[Entity]:
        """
        Get the `Entity` with matching ``ty`` and ``id``.

        The following groups of ``ty`` should be treated to be equivalent, that is, for a given
        ``ty`` and ``id``, if the ``ty`` is in a given group, a matching ``hash`` with that ``id``
        from within any ``ty`` in that group should be returned.

        * `EntityType.USER` and `EntityType.BOT`.
        * `EntityType.GROUP`.
        * `EntityType.CHANNEL`, `EntityType.MEGAGROUP` and `EntityType.GIGAGROUP`.

        For example, if a ``ty`` representing a bot is stored but the asking ``ty`` is a user,
        the corresponding ``hash`` should still be returned.

        You may use ``EntityType.canonical`` to find out the canonical type.

        A ``ty`` with the value of ``None`` should be treated as "any entity with matching ID".
        """
        raise NotImplementedError

    @abstractmethod
    async def save(self):
        """
        Save the session.

        May do nothing if the other methods already saved when they were called.

        May return custom data when manual saving is intended.
        """
        raise NotImplementedError
