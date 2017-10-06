from threading import Lock

import re

from .. import utils
from ..tl import TLObject
from ..tl.types import (
    User, Chat, Channel, PeerUser, PeerChat, PeerChannel,
    InputPeerUser, InputPeerChat, InputPeerChannel
)


class EntityDatabase:
    def __init__(self, input_list=None, enabled=True, enabled_full=True):
        """Creates a new entity database with an initial load of "Input"
           entities, if any.

           If 'enabled', input entities will be saved. The whole entity
           will be saved if both 'enabled' and 'enabled_full' are True.
        """
        self.enabled = enabled
        self.enabled_full = enabled_full

        self._lock = Lock()
        self._entities = {}  # marked_id: user|chat|channel

        if input_list:
            self._input_entities = {k: v for k, v in input_list}
        else:
            self._input_entities = {}  # marked_id: hash

        # TODO Allow disabling some extra mappings
        self._username_id = {}  # username: marked_id
        self._phone_id = {}  # phone: marked_id

    def process(self, tlobject):
        """Processes all the found entities on the given TLObject,
           unless .enabled is False.

           Returns True if new input entities were added.
        """
        if not self.enabled:
            return False

        # Save all input entities we know of
        if not isinstance(tlobject, TLObject) and hasattr(tlobject, '__iter__'):
            # This may be a list of users already for instance
            return self.expand(tlobject)

        entities = []
        if hasattr(tlobject, 'chats') and hasattr(tlobject.chats, '__iter__'):
            entities.extend(tlobject.chats)
        if hasattr(tlobject, 'users') and hasattr(tlobject.users, '__iter__'):
            entities.extend(tlobject.users)

        return self.expand(entities)

    def expand(self, entities):
        """Adds new input entities to the local database unconditionally.
           Unknown types will be ignored.
        """
        if not entities or not self.enabled:
            return False

        new = []  # Array of entities (User, Chat, or Channel)
        new_input = {}  # Dictionary of {entity_marked_id: access_hash}
        for e in entities:
            if not isinstance(e, TLObject):
                continue

            try:
                p = utils.get_input_peer(e, allow_self=False)
                new_input[utils.get_peer_id(p, add_mark=True)] = \
                    getattr(p, 'access_hash', 0)  # chats won't have hash

                if self.enabled_full:
                    if isinstance(e, User) \
                            or isinstance(e, Chat) \
                            or isinstance(e, Channel):
                        new.append(e)
            except ValueError:
                pass

        with self._lock:
            before = len(self._input_entities)
            self._input_entities.update(new_input)
            for e in new:
                self._add_full_entity(e)
            return len(self._input_entities) != before

    def _add_full_entity(self, entity):
        """Adds a "full" entity (User, Chat or Channel, not "Input*"),
           despite the value of self.enabled and self.enabled_full.

           Not to be confused with UserFull, ChatFull, or ChannelFull,
           "full" means simply not "Input*".
        """
        marked_id = utils.get_peer_id(
            utils.get_input_peer(entity, allow_self=False), add_mark=True
        )
        try:
            old_entity = self._entities[marked_id]
            old_entity.__dict__.update(entity.__dict__)  # Keep old references

            # Update must delete old username and phone
            username = getattr(old_entity, 'username', None)
            if username:
                del self._username_id[username.lower()]

            phone = getattr(old_entity, 'phone', None)
            if phone:
                del self._phone_id[phone]
        except KeyError:
            # Add new entity
            self._entities[marked_id] = entity

        # Always update username or phone if any
        username = getattr(entity, 'username', None)
        if username:
            self._username_id[username.lower()] = marked_id

        phone = getattr(entity, 'phone', None)
        if phone:
            self._username_id[phone] = marked_id

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
            phone = EntityDatabase.parse_phone(key)
            if phone:
                return self._phone_id[phone]
            else:
                key = key.lstrip('@').lower()
                return self._entities[self._username_id[key]]

        if isinstance(key, int):
            return self._entities[key]  # normal IDs are assumed users

        if isinstance(key, TLObject):
            sc = type(key).SUBCLASS_OF_ID
            if sc == 0x2d45687:
                # Subclass of "Peer"
                return self._entities[utils.get_peer_id(key, add_mark=True)]
            elif sc in {0x2da17977, 0xc5af5d94, 0x6d44b7db}:
                # Subclass of "User", "Chat" or "Channel"
                return key

        raise KeyError(key)

    def __delitem__(self, key):
        target = self[key]
        del self._entities[key]
        if getattr(target, 'username'):
            del self._username_id[target.username]

    # TODO Allow search by name by tokenizing the input and return a list

    @staticmethod
    def parse_phone(phone):
        """Parses the given phone, or returns None if it's invalid"""
        if isinstance(phone, int):
            return str(phone)
        else:
            phone = re.sub(r'[+()\s-]', '', str(phone))
            if phone.isdigit():
                return phone

    def get_input_entity(self, peer):
        try:
            i, k = utils.get_peer_id(peer, add_mark=True, get_kind=True)
            h = self._input_entities[i]
            if k == PeerUser:
                return InputPeerUser(i, h)
            elif k == PeerChat:
                return InputPeerChat(i)
            elif k == PeerChannel:
                return InputPeerChannel(i, h)

        except ValueError as e:
            raise KeyError(peer) from e
        raise KeyError(peer)

    def get_input_list(self):
        return list(self._input_entities.items())

    def clear(self, target=None):
        if target is None:
            self._entities.clear()
        else:
            del self[target]
