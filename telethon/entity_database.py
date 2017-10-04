from . import utils
from .tl import TLObject


class EntityDatabase:
    def __init__(self, enabled=True):
        self.enabled = enabled

        self._entities = {}  # marked_id: user|chat|channel

        # TODO Allow disabling some extra mappings
        self._username_id = {}  # username: marked_id

    def add(self, entity):
        if not self.enabled:
            return

        # Adds or updates the given entity
        marked_id = utils.get_peer_id(entity, add_mark=True)
        try:
            old_entity = self._entities[marked_id]
            old_entity.__dict__.update(entity)  # Keep old references

            # Update must delete old username
            username = getattr(old_entity, 'username', None)
            if username:
                del self._username_id[username.lower()]
        except KeyError:
            # Add new entity
            self._entities[marked_id] = entity

        # Always update username if any
        username = getattr(entity, 'username', None)
        if username:
            self._username_id[username.lower()] = marked_id

    def __getitem__(self, key):
        """Accepts a digit only string as phone number,
           otherwise it's treated as an username.

           If an integer is given, it's treated as the ID of the desired User.
           The ID given won't try to be guessed as the ID of a chat or channel,
           as there may be an user with that ID, and it would be unreliable.

           If a Peer is given (PeerUser, PeerChat, PeerChannel),
           its specific entity is retrieved as User, Chat or Channel.
           Note that megagroups are channels with .megagroup = True.
        """
        if isinstance(key, str):
            # TODO Parse phone properly, currently only usernames
            key = key.lstrip('@').lower()
            # TODO Use the client to return from username if not found
            return self._entities[self._username_id[key]]

        if isinstance(key, int):
            return self._entities[key]  # normal IDs are assumed users

        if isinstance(key, TLObject) and type(key).SUBCLASS_OF_ID == 0x2d45687:
            return self._entities[utils.get_peer_id(key, add_mark=True)]

        raise KeyError(key)

    def __delitem__(self, key):
        target = self[key]
        del self._entities[key]
        if getattr(target, 'username'):
            del self._username_id[target.username]

    # TODO Allow search by name by tokenizing the input and return a list

    def clear(self, target=None):
        if target is None:
            self._entities.clear()
        else:
            del self[target]
