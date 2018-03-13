
from .memory import MemorySession, _SentFileType
from ..crypto import AuthKey
from .. import utils
from ..tl.types import (
    InputPhoto, InputDocument, PeerUser, PeerChat, PeerChannel
)
import logging
import json
import base64
import time
import redis
import pickle

TS_STR_FORMAT = "%F %T"
HIVE_PREFIX = "telethon:client"
PACK_FUNC = "json"
UNPACK_FUNC = "json"


__log__ = logging.getLogger(__name__)


class RedisSession(MemorySession):

    log = None
    session_name = None
    redis_connection = None
    hive_prefix = None
    sess_prefix = None
    pack_func = None
    unpack_func = None

    def __init__(self, session_name=None, redis_connection=None, hive_prefix=None,
                 pack_func=PACK_FUNC, unpack_func=UNPACK_FUNC):
        if not isinstance(session_name, (str, bytes)):
            raise TypeError("Session name must be a string or bytes")

        if not redis_connection or not isinstance(redis_connection, redis.StrictRedis):
            raise TypeError('The given redis_connection must be a Redis instance.')

        super().__init__()

        self.session_name = session_name if isinstance(session_name, str) else session_name.decode()
        self.redis_connection = redis_connection

        self.hive_prefix = hive_prefix or HIVE_PREFIX
        self.pack_func = pack_func
        self.unpack_func = unpack_func

        self.sess_prefix = "{}:{}".format(self.hive_prefix, self.session_name)

        self.save_entities = True

        self.feed_sessions()

    def _pack(self, o, **kwargs):
        if self.pack_func == "json":
            kwargs["indent"] = 2
        return json.dumps(o, **kwargs) if self.pack_func == "json" else pickle.dumps(o, **kwargs)

    def _unpack(self, o, **kwargs):
        return json.loads(o, **kwargs) if self.unpack_func == "json" else pickle.loads(o, **kwargs)

    def feed_sessions(self):
        try:
            s = self._get_sessions()
            if len(s) == 0:
                self._auth_key = AuthKey(data=bytes())
                return

            s = self.redis_connection.get(s[-1])
            if not s:
                # No sessions
                self._auth_key = AuthKey(data=bytes())
                return

            s = self._unpack(s)
            self._dc_id = s["dc_id"]
            self._server_address = s["server_address"]
            self._port = s["port"]
            auth_key = base64.standard_b64decode(s["auth_key"])
            self._auth_key = AuthKey(data=auth_key)
        except Exception as ex:
            __log__.exception(ex.args)

    def _update_sessions(self):
        """
        Stores session into redis.
        """
        auth_key = self._auth_key.key if self._auth_key else bytes()
        if not self._dc_id:
            return

        s = {
            "dc_id": self._dc_id,
            "server_address": self._server_address,
            "port": self._port,
            "auth_key": base64.standard_b64encode(auth_key).decode(),
            "ts_ts": time.time(),
            "ts_str": time.strftime(TS_STR_FORMAT, time.localtime()),
        }

        key = "{}:sessions:{}".format(self.sess_prefix, self._dc_id)
        try:
            self.redis_connection.set(key, self._pack(s))
        except Exception as ex:
            __log__.exception(ex.args)

    def set_dc(self, dc_id, server_address, port):
        """
        Sets the information of the data center address and port that
        the library should connect to, as well as the data center ID,
        which is currently unused.
        """
        super().set_dc(dc_id, server_address, port)
        self._update_sessions()

        auth_key = bytes()

        if not self._dc_id:
            self._auth_key = AuthKey(data=auth_key)
            return

        key = "{}:sessions:{}".format(self.sess_prefix, self._dc_id)
        s = self.redis_connection.get(key)
        if s:
            s = self._unpack(s)
            auth_key = base64.standard_b64decode(s["auth_key"])
        self._auth_key = AuthKey(data=auth_key)

    @MemorySession.auth_key.setter
    def auth_key(self, value):
        """
        Sets the ``AuthKey`` to be used for the saved data center.
        """
        self._auth_key = value
        self._update_sessions()

    def list_sessions(self):
        """
        Lists available sessions. Not used by the library itself.
        """
        return self._get_sessions(strip_prefix=True)

    def process_entities(self, tlo):
        """
        Processes the input ``TLObject`` or ``list`` and saves
        whatever information is relevant (e.g., ID or access hash).
        """

        if not self.save_entities:
            return

        rows = self._entities_to_rows(tlo)
        if not rows or len(rows) == 0 or len(rows[0]) == 0:
            return

        try:
            rows = rows[0]
            key = "{}:entities:{}".format(self.sess_prefix, rows[0])
            s = {
                "id": rows[0],
                "hash": rows[1],
                "username": rows[2],
                "phone": rows[3],
                "name": rows[4],
                "ts_ts": time.time(),
                "ts_str": time.strftime(TS_STR_FORMAT, time.localtime()),
            }
            self.redis_connection.set(key, self._pack(s))
        except Exception as ex:
            __log__.exception(ex.args)

    def _get_entities(self, strip_prefix=False):
        """
        Returns list of entities. if strip_prefix is False - returns redis keys,
        else returns list of id's
        """
        key_pattern = "{}:{}:entities:".format(self.hive_prefix, self.session_name)
        try:
            entities = self.redis_connection.keys(key_pattern+"*")
            if not strip_prefix:
                return entities
            return [s.decode().replace(key_pattern, "") for s in entities]
        except Exception as ex:
            __log__.exception(ex.args)
            return []

    def _get_sessions(self, strip_prefix=False):
        """
        Returns list of sessions. if strip_prefix is False - returns redis keys,
        else returns list of id's
        """
        key_pattern = "{}:{}:sessions:".format(self.hive_prefix, self.session_name)
        try:
            sessions = self.redis_connection.keys(key_pattern+"*")
            return [s.decode().replace(key_pattern, "") if strip_prefix else s.decode() for s in sessions]
        except Exception as ex:
            __log__.exception(ex.args)
            return []

    def get_entity_rows_by_phone(self, phone):
        try:
            for key in self._get_entities():
                entity = self._unpack(self.redis_connection.get(key))
                if "phone" in entity and entity["phone"] == phone:
                    return entity["id"], entity["hash"]
        except Exception as ex:
            __log__.exception(ex.args)
        return None

    def get_entity_rows_by_username(self, username):
        try:
            for key in self._get_entities():
                entity = self._unpack(self.redis_connection.get(key))
                if "username" in entity and entity["username"] == username:
                    return entity["id"], entity["hash"]
        except Exception as ex:
            __log__.exception(ex.args)
        return None

    def get_entity_rows_by_name(self, name):
        try:
            for key in self._get_entities():
                entity = self._unpack(self.redis_connection.get(key))
                if "name" in entity and entity["name"] == name:
                    return entity["id"], entity["hash"]
        except Exception as ex:
            __log__.exception(ex.args)

        return None

    def get_entity_rows_by_id(self, entity_id, exact=True):
        if exact:
            key = "{}:entities:{}".format(self.sess_prefix, entity_id)
            s = self.redis_connection.get(key)
            if not s:
                return None
            try:
                s = self._unpack(s)
                return entity_id, s["hash"]
            except Exception as ex:
                __log__.exception(ex.args)
                return None
        else:
            ids = (
                utils.get_peer_id(PeerUser(entity_id)),
                utils.get_peer_id(PeerChat(entity_id)),
                utils.get_peer_id(PeerChannel(entity_id))
            )

            try:
                for key in self._get_entities():
                    entity = self._unpack(self.redis_connection.get(key))
                    if "id" in entity and entity["id"] in ids:
                        return entity["id"], entity["hash"]
            except Exception as ex:
                __log__.exception(ex.args)

    def get_file(self, md5_digest, file_size, cls):
        key = "{}:sent_files:{}".format(self.sess_prefix, md5_digest)
        s = self.redis_connection.get(key)
        if s:
            try:
                s = self._unpack(s)
                return md5_digest, file_size \
                    if s["file_size"] == file_size and s["type"] == _SentFileType.from_type(cls).value \
                    else None
            except Exception as ex:
                __log__.exception(ex.args)
                return None

    def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache {} instance'.format(type(instance)))

        key = "{}:sent_files:{}".format(self.sess_prefix, md5_digest)
        s = {
            "md5_digest": md5_digest,
            "file_size": file_size,
            "type": _SentFileType.from_type(type(instance)).value,
            "id": instance.id,
            "hash": instance.access_hash,
            "ts_ts": time.time(),
            "ts_str": time.strftime(TS_STR_FORMAT, time.localtime()),
        }
        try:
            self.redis_connection.set(key, self._pack(s))
        except Exception as ex:
            __log__.exception(ex.args)

