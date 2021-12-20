from enum import Enum

from .abstract import Session
from .. import utils
from ..tl import TLObject
from ..tl.types import (
    PeerUser, PeerChat, PeerChannel,
    InputPeerUser, InputPeerChat, InputPeerChannel,
    InputPhoto, InputDocument
)


class _SentFileType(Enum):
    DOCUMENT = 0
    PHOTO = 1

    @staticmethod
    def from_type(cls):
        if cls == InputDocument:
            return _SentFileType.DOCUMENT
        elif cls == InputPhoto:
            return _SentFileType.PHOTO
        else:
            raise ValueError('The cls must be either InputDocument/InputPhoto')


class MemorySession(Session):
    def __init__(self):
        super().__init__()

        self._dc_id = 0
        self._server_address = None
        self._port = None
        self._auth_key = None
        self._takeout_id = None

        self._files = {}
        self._entities = set()
        self._update_states = {}

    def set_dc(self, dc_id, server_address, port):
        self._dc_id = dc_id or 0
        self._server_address = server_address
        self._port = port

    @property
    def dc_id(self):
        return self._dc_id

    @property
    def server_address(self):
        return self._server_address

    @property
    def port(self):
        return self._port

    @property
    def auth_key(self):
        return self._auth_key

    @auth_key.setter
    def auth_key(self, value):
        self._auth_key = value

    @property
    def takeout_id(self):
        return self._takeout_id

    @takeout_id.setter
    def takeout_id(self, value):
        self._takeout_id = value

    async def get_update_state(self, entity_id):
        return self._update_states.get(entity_id, None)

    async def set_update_state(self, entity_id, state):
        self._update_states[entity_id] = state

    async def close(self):
        pass

    async def save(self):
        pass

    async def delete(self):
        pass

    @staticmethod
    def _entity_values_to_row(id, hash, username, phone, name):
        # While this is a simple implementation it might be overrode by,
        # other classes so they don't need to implement the plural form
        # of the method. Don't remove.
        return id, hash, username, phone, name

    def _entity_to_row(self, e):
        if not isinstance(e, TLObject):
            return
        try:
            p = utils.get_input_peer(e, allow_self=False)
            marked_id = utils.get_peer_id(p)
        except TypeError:
            # Note: `get_input_peer` already checks for non-zero `access_hash`.
            #        See issues #354 and #392. It also checks that the entity
            #        is not `min`, because its `access_hash` cannot be used
            #        anywhere (since layer 102, there are two access hashes).
            return

        if isinstance(p, (InputPeerUser, InputPeerChannel)):
            p_hash = p.access_hash
        elif isinstance(p, InputPeerChat):
            p_hash = 0
        else:
            return

        username = getattr(e, 'username', None) or None
        if username is not None:
            username = username.lower()
        phone = getattr(e, 'phone', None)
        name = utils.get_display_name(e) or None
        return self._entity_values_to_row(
            marked_id, p_hash, username, phone, name
        )

    def _entities_to_rows(self, tlo):
        if not isinstance(tlo, TLObject) and utils.is_list_like(tlo):
            # This may be a list of users already for instance
            entities = tlo
        else:
            entities = []
            if hasattr(tlo, 'user'):
                entities.append(tlo.user)
            if hasattr(tlo, 'chat'):
                entities.append(tlo.chat)
            if hasattr(tlo, 'chats') and utils.is_list_like(tlo.chats):
                entities.extend(tlo.chats)
            if hasattr(tlo, 'users') and utils.is_list_like(tlo.users):
                entities.extend(tlo.users)

        rows = []  # Rows to add (id, hash, username, phone, name)
        for e in entities:
            row = self._entity_to_row(e)
            if row:
                rows.append(row)
        return rows

    async def process_entities(self, tlo):
        self._entities |= set(self._entities_to_rows(tlo))

    async def get_entity_rows_by_phone(self, phone):
        try:
            return next((id, hash) for id, hash, _, found_phone, _
                        in self._entities if found_phone == phone)
        except StopIteration:
            pass

    async def get_entity_rows_by_username(self, username):
        try:
            return next((id, hash) for id, hash, found_username, _, _
                        in self._entities if found_username == username)
        except StopIteration:
            pass

    async def get_entity_rows_by_name(self, name):
        try:
            return next((id, hash) for id, hash, _, _, found_name
                        in self._entities if found_name == name)
        except StopIteration:
            pass

    async def get_entity_rows_by_id(self, id, exact=True):
        try:
            if exact:
                return next((id, hash) for found_id, hash, _, _, _
                            in self._entities if found_id == id)
            else:
                ids = (
                    utils.get_peer_id(PeerUser(id)),
                    utils.get_peer_id(PeerChat(id)),
                    utils.get_peer_id(PeerChannel(id))
                )
                return next((id, hash) for found_id, hash, _, _, _
                            in self._entities if found_id in ids)
        except StopIteration:
            pass

    async def get_input_entity(self, key):
        try:
            if key.SUBCLASS_OF_ID in (0xc91c90b6, 0xe669bf46, 0x40f202fd):
                # hex(crc32(b'InputPeer', b'InputUser' and b'InputChannel'))
                # We already have an Input version, so nothing else required
                return key
            # Try to early return if this key can be casted as input peer
            return utils.get_input_peer(key)
        except (AttributeError, TypeError):
            # Not a TLObject or can't be cast into InputPeer
            if isinstance(key, TLObject):
                key = utils.get_peer_id(key)
                exact = True
            else:
                exact = not isinstance(key, int) or key < 0

        result = None
        if isinstance(key, str):
            phone = utils.parse_phone(key)
            if phone:
                result = await self.get_entity_rows_by_phone(phone)
            else:
                username, invite = utils.parse_username(key)
                if username and not invite:
                    result = await self.get_entity_rows_by_username(username)
                else:
                    tup = utils.resolve_invite_link(key)[1]
                    if tup:
                        result = await self.get_entity_rows_by_id(tup, exact=False)

        elif isinstance(key, int):
            result = await self.get_entity_rows_by_id(key, exact)

        if not result and isinstance(key, str):
            result = await self.get_entity_rows_by_name(key)

        if result:
            entity_id, entity_hash = result  # unpack resulting tuple
            entity_id, kind = utils.resolve_id(entity_id)
            # removes the mark and returns type of entity
            if kind == PeerUser:
                return InputPeerUser(entity_id, entity_hash)
            elif kind == PeerChat:
                return InputPeerChat(entity_id)
            elif kind == PeerChannel:
                return InputPeerChannel(entity_id, entity_hash)
        else:
            raise ValueError('Could not find input entity with key ', key)

    async def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache %s instance' % type(instance))
        key = (md5_digest, file_size, _SentFileType.from_type(type(instance)))
        value = (instance.id, instance.access_hash)
        self._files[key] = value

    async def get_file(self, md5_digest, file_size, cls):
        key = (md5_digest, file_size, _SentFileType.from_type(cls))
        try:
            return cls(*self._files[key])
        except KeyError:
            return None
