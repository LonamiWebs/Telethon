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

        self._files = {}
        self._entities = set()

    def set_dc(self, dc_id, server_address, port):
        self._dc_id = dc_id or 0
        self._server_address = server_address
        self._port = port

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

    def close(self):
        pass

    def save(self):
        pass

    def delete(self):
        pass

    def _entity_values_to_row(self, id, hash, username, phone, name):
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
            return

        if isinstance(p, (InputPeerUser, InputPeerChannel)):
            if not p.access_hash:
                # Some users and channels seem to be returned without
                # an 'access_hash', meaning Telegram doesn't want you
                # to access them. This is the reason behind ensuring
                # that the 'access_hash' is non-zero. See issue #354.
                # Note that this checks for zero or None, see #392.
                return
            else:
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

    def process_entities(self, tlo):
        self._entities |= set(self._entities_to_rows(tlo))

    def get_entity_rows_by_phone(self, phone):
        try:
            return next((id, hash) for id, hash, _, found_phone, _
                        in self._entities if found_phone == phone)
        except StopIteration:
            pass

    def get_entity_rows_by_username(self, username):
        try:
            return next((id, hash) for id, hash, found_username, _, _
                        in self._entities if found_username == username)
        except StopIteration:
            pass

    def get_entity_rows_by_name(self, name):
        try:
            return next((id, hash) for id, hash, _, _, found_name
                        in self._entities if found_name == name)
        except StopIteration:
            pass

    def get_entity_rows_by_id(self, id, exact=True):
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

    def get_input_entity(self, key):
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
                result = self.get_entity_rows_by_phone(phone)
            else:
                username, _ = utils.parse_username(key)
                if username:
                    result = self.get_entity_rows_by_username(username)

        elif isinstance(key, int):
            result = self.get_entity_rows_by_id(key, exact)

        if not result and isinstance(key, str):
            result = self.get_entity_rows_by_name(key)

        if result:
            i, h = result  # unpack resulting tuple
            i, k = utils.resolve_id(i)  # removes the mark and returns kind
            if k == PeerUser:
                return InputPeerUser(i, h)
            elif k == PeerChat:
                return InputPeerChat(i)
            elif k == PeerChannel:
                return InputPeerChannel(i, h)
        else:
            raise ValueError('Could not find input entity with key ', key)

    def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache %s instance' % type(instance))
        key = (md5_digest, file_size, _SentFileType.from_type(instance))
        value = (instance.id, instance.access_hash)
        self._files[key] = value

    def get_file(self, md5_digest, file_size, cls):
        key = (md5_digest, file_size, _SentFileType.from_type(cls))
        try:
            return cls(self._files[key])
        except KeyError:
            return None
