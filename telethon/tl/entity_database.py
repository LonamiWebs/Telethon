import re
from threading import Lock

from ..tl import TLObject
from ..tl.types import (
    User, Chat, Channel, PeerUser, PeerChat, PeerChannel,
    InputPeerUser, InputPeerChat, InputPeerChannel
)
from .. import utils  # Keep this line the last to maybe fix #357


USERNAME_RE = re.compile(
    r'@|(?:https?://)?(?:telegram\.(?:me|dog)|t\.me)/(joinchat/)?'
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
            # TODO For compatibility reasons some sessions were saved with
            # 'access_hash': null in the JSON session file. Drop these, as
            # it means we don't have access to such InputPeers. Issue #354.
            self._input_entities = {
                k: v for k, v in input_list if v is not None
            }
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
                marked_id = utils.get_peer_id(p, add_mark=True)

                has_hash = False
                if isinstance(p, InputPeerChat):
                    # Chats don't have a hash
                    new_input[marked_id] = 0
                    has_hash = True
                elif p.access_hash:
                    # Some users and channels seem to be returned without
                    # an 'access_hash', meaning Telegram doesn't want you
                    # to access them. This is the reason behind ensuring
                    # that the 'access_hash' is non-zero. See issue #354.
                    new_input[marked_id] = p.access_hash
                    has_hash = True

                if self.enabled_full and has_hash:
                    if isinstance(e, (User, Chat, Channel)):
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
            self._phone_id[phone] = marked_id

    def _parse_key(self, key):
        """Parses the given string, integer or TLObject key into a
           marked user ID ready for use on self._entities.

           If a callable key is given, the entity will be passed to the
           function, and if it returns a true-like value, the marked ID
           for such entity will be returned.

           Raises ValueError if it cannot be parsed.
        """
        if isinstance(key, str):
            phone = EntityDatabase.parse_phone(key)
            try:
                if phone:
                    return self._phone_id[phone]
                else:
                    username, _ = EntityDatabase.parse_username(key)
                    return self._username_id[username.lower()]
            except KeyError as e:
                raise ValueError() from e

        if isinstance(key, int):
            return key  # normal IDs are assumed users

        if isinstance(key, TLObject):
            return utils.get_peer_id(key, add_mark=True)

        if callable(key):
            for k, v in self._entities.items():
                if key(v):
                    return k

        raise ValueError()

    def __getitem__(self, key):
        """See the ._parse_key() docstring for possible values of the key"""
        try:
            return self._entities[self._parse_key(key)]
        except (ValueError, KeyError) as e:
            raise KeyError(key) from e

    def __delitem__(self, key):
        try:
            old = self._entities.pop(self._parse_key(key))
            # Try removing the username and phone (if pop didn't fail),
            # since the entity may have no username or phone, just ignore
            # errors. It should be there if we popped the entity correctly.
            try:
                del self._username_id[getattr(old, 'username', None)]
            except KeyError:
                pass

            try:
                del self._phone_id[getattr(old, 'phone', None)]
            except KeyError:
                pass

        except (ValueError, KeyError) as e:
            raise KeyError(key) from e

    @staticmethod
    def parse_phone(phone):
        """Parses the given phone, or returns None if it's invalid"""
        if isinstance(phone, int):
            return str(phone)
        else:
            phone = re.sub(r'[+()\s-]', '', str(phone))
            if phone.isdigit():
                return phone

    @staticmethod
    def parse_username(username):
        """Parses the given username or channel access hash, given
           a string, username or URL. Returns a tuple consisting of
           both the stripped username and whether it is a joinchat/ hash.
        """
        username = username.strip()
        m = USERNAME_RE.match(username)
        if m:
            return username[m.end():], bool(m.group(1))
        else:
            return username, False

    def get_input_entity(self, peer):
        try:
            i = utils.get_peer_id(peer, add_mark=True)
            h = self._input_entities[i]  # we store the IDs marked
            i, k = utils.resolve_id(i)  # removes the mark and returns kind

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
