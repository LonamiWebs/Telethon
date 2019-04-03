import itertools
from . import utils
from .tl import types


class EntityCache:
    """
    In-memory input entity cache, defaultdict-like behaviour.
    """
    def add(self, entities):
        """
        Adds the given entities to the cache, if they weren't saved before.
        """
        if not utils.is_list_like(entities):
            # Invariant: all "chats" and "users" are always iterables,
            # and "user" never is (so we wrap it inside a list).
            entities = itertools.chain(
                getattr(entities, 'chats', []),
                getattr(entities, 'users', []),
                (hasattr(entities, 'user') and [entities.user]) or []
            )

        for entity in entities:
            try:
                pid = utils.get_peer_id(entity)
                if pid not in self.__dict__:
                    # Note: `get_input_peer` already checks for `access_hash`
                    self.__dict__[pid] = utils.get_input_peer(entity)
            except TypeError:
                pass

    def __getitem__(self, item):
        """
        Gets the corresponding :tl:`InputPeer` for the given ID or peer,
        or raises ``KeyError`` on any error (i.e. cannot be found).
        """
        if not isinstance(item, int) or item < 0:
            try:
                return self.__dict__[utils.get_peer_id(item)]
            except TypeError:
                raise KeyError('Invalid key will not have entity') from None

        for cls in (types.PeerUser, types.PeerChat, types.PeerChannel):
            result = self.__dict__.get(utils.get_peer_id(cls(item)))
            if result:
                return result

        raise KeyError('No cached entity for the given key')
