import json
import os
import platform
import sqlite3
import struct
import time
from base64 import b64decode
from enum import Enum
from os.path import isfile as file_exists
from threading import Lock, RLock

from . import utils
from .crypto import AuthKey
from .tl import TLObject
from .tl.types import (
    PeerUser, PeerChat, PeerChannel,
    InputPeerUser, InputPeerChat, InputPeerChannel,
    InputPhoto, InputDocument
)

EXTENSION = '.session'
CURRENT_VERSION = 3  # database version


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


class Session:
    """This session contains the required information to login into your
       Telegram account. NEVER give the saved JSON file to anyone, since
       they would gain instant access to all your messages and contacts.

       If you think the session has been compromised, close all the sessions
       through an official Telegram client to revoke the authorization.
    """
    def __init__(self, session_id):
        """session_user_id should either be a string or another Session.
           Note that if another session is given, only parameters like
           those required to init a connection will be copied.
        """
        # These values will NOT be saved
        self.filename = ':memory:'

        # For connection purposes
        if isinstance(session_id, Session):
            self.device_model = session_id.device_model
            self.system_version = session_id.system_version
            self.app_version = session_id.app_version
            self.lang_code = session_id.lang_code
            self.system_lang_code = session_id.system_lang_code
            self.lang_pack = session_id.lang_pack
            self.report_errors = session_id.report_errors
            self.save_entities = session_id.save_entities
            self.flood_sleep_threshold = session_id.flood_sleep_threshold
        else:  # str / None
            if session_id:
                self.filename = session_id
                if not self.filename.endswith(EXTENSION):
                    self.filename += EXTENSION

            system = platform.uname()
            self.device_model = system.system or 'Unknown'
            self.system_version = system.release or '1.0'
            self.app_version = '1.0'  # '0' will provoke error
            self.lang_code = 'en'
            self.system_lang_code = self.lang_code
            self.lang_pack = ''
            self.report_errors = True
            self.save_entities = True
            self.flood_sleep_threshold = 60

        self.id = struct.unpack('q', os.urandom(8))[0]
        self._sequence = 0
        self.time_offset = 0
        self._last_msg_id = 0  # Long
        self.salt = 0  # Long

        # Cross-thread safety
        self._seq_no_lock = Lock()
        self._msg_id_lock = Lock()
        self._db_lock = RLock()

        # These values will be saved
        self._dc_id = 0
        self._server_address = None
        self._port = None
        self._auth_key = None

        # Migrating from .json -> SQL
        entities = self._check_migrate_json()

        self._conn = None
        c = self._cursor()
        c.execute("select name from sqlite_master "
                  "where type='table' and name='version'")
        if c.fetchone():
            # Tables already exist, check for the version
            c.execute("select version from version")
            version = c.fetchone()[0]
            if version != CURRENT_VERSION:
                self._upgrade_database(old=version)
                c.execute("delete from version")
                c.execute("insert into version values (?)", (CURRENT_VERSION,))
                self.save()

            # These values will be saved
            c.execute('select * from sessions')
            tuple_ = c.fetchone()
            if tuple_:
                self._dc_id, self._server_address, self._port, key, = tuple_
                self._auth_key = AuthKey(data=key)

            c.close()
        else:
            # Tables don't exist, create new ones
            self._create_table(
                c,
                "version (version integer primary key)"
                ,
                """sessions (
                    dc_id integer primary key,
                    server_address text,
                    port integer,
                    auth_key blob
                )"""
                ,
                """entities (
                    id integer primary key,
                    hash integer not null,
                    username text,
                    phone integer,
                    name text
                )"""
                ,
                """sent_files (
                    md5_digest blob,
                    file_size integer,
                    type integer,
                    id integer,
                    hash integer,
                    primary key(md5_digest, file_size, type)
                )"""
            )
            c.execute("insert into version values (?)", (CURRENT_VERSION,))
            # Migrating from JSON -> new table and may have entities
            if entities:
                c.executemany(
                    'insert or replace into entities values (?,?,?,?,?)',
                    entities
                )
            self._update_session_table()
            c.close()
            self.save()

    def _check_migrate_json(self):
        if file_exists(self.filename):
            try:
                with open(self.filename, encoding='utf-8') as f:
                    data = json.load(f)
                self.delete()  # Delete JSON file to create database

                self._port = data.get('port', self._port)
                self._server_address = \
                    data.get('server_address', self._server_address)

                if data.get('auth_key_data', None) is not None:
                    key = b64decode(data['auth_key_data'])
                    self._auth_key = AuthKey(data=key)

                rows = []
                for p_id, p_hash in data.get('entities', []):
                    if p_hash is not None:
                        rows.append((p_id, p_hash, None, None, None))
                return rows
            except UnicodeDecodeError:
                return []  # No entities

    def _upgrade_database(self, old):
        c = self._cursor()
        # old == 1 doesn't have the old sent_files so no need to drop
        if old == 2:
            # Old cache from old sent_files lasts then a day anyway, drop
            c.execute('drop table sent_files')
        self._create_table(c, """sent_files (
            md5_digest blob,
            file_size integer,
            type integer,
            id integer,
            hash integer,
            primary key(md5_digest, file_size, type)
        )""")
        c.close()

    @staticmethod
    def _create_table(c, *definitions):
        """
        Creates a table given its definition 'name (columns).
        If the sqlite version is >= 3.8.2, it will use "without rowid".
        See http://www.sqlite.org/releaselog/3_8_2.html.
        """
        required = (3, 8, 2)
        sqlite_v = tuple(int(x) for x in sqlite3.sqlite_version.split('.'))
        extra = ' without rowid' if sqlite_v >= required else ''
        for definition in definitions:
            c.execute('create table {}{}'.format(definition, extra))

    # Data from sessions should be kept as properties
    # not to fetch the database every time we need it
    def set_dc(self, dc_id, server_address, port):
        self._dc_id = dc_id
        self._server_address = server_address
        self._port = port
        self._update_session_table()

        # Fetch the auth_key corresponding to this data center
        c = self._cursor()
        c.execute('select auth_key from sessions')
        tuple_ = c.fetchone()
        if tuple_:
            self._auth_key = AuthKey(data=tuple_[0])
        else:
            self._auth_key = None
        c.close()

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
        self._update_session_table()

    def _update_session_table(self):
        with self._db_lock:
            c = self._cursor()
            # While we can save multiple rows into the sessions table
            # currently we only want to keep ONE as the tables don't
            # tell us which auth_key's are usable and will work. Needs
            # some more work before being able to save auth_key's for
            # multiple DCs. Probably done differently.
            c.execute('delete from sessions')
            c.execute('insert or replace into sessions values (?,?,?,?)', (
                self._dc_id,
                self._server_address,
                self._port,
                self._auth_key.key if self._auth_key else b''
            ))
            c.close()

    def save(self):
        """Saves the current session object as session_user_id.session"""
        with self._db_lock:
            self._conn.commit()

    def _cursor(self):
        """Asserts that the connection is open and returns a cursor"""
        with self._db_lock:
            if self._conn is None:
                self._conn = sqlite3.connect(self.filename,
                                             check_same_thread=False)
            return self._conn.cursor()

    def close(self):
        """Closes the connection unless we're working in-memory"""
        if self.filename != ':memory:':
            with self._db_lock:
                if self._conn is not None:
                    self._conn.close()
                    self._conn = None

    def delete(self):
        """Deletes the current session file"""
        if self.filename == ':memory:':
            return True
        try:
            os.remove(self.filename)
            return True
        except OSError:
            return False

    @staticmethod
    def list_sessions():
        """Lists all the sessions of the users who have ever connected
           using this client and never logged out
        """
        return [os.path.splitext(os.path.basename(f))[0]
                for f in os.listdir('.') if f.endswith(EXTENSION)]

    def generate_sequence(self, content_related):
        """Thread safe method to generates the next sequence number,
           based on whether it was confirmed yet or not.

           Note that if confirmed=True, the sequence number
           will be increased by one too
        """
        with self._seq_no_lock:
            if content_related:
                result = self._sequence * 2 + 1
                self._sequence += 1
                return result
            else:
                return self._sequence * 2

    def get_new_msg_id(self):
        """Generates a new unique message ID based on the current
           time (in ms) since epoch"""
        # Refer to mtproto_plain_sender.py for the original method
        now = time.time()
        nanoseconds = int((now - int(now)) * 1e+9)
        # "message identifiers are divisible by 4"
        new_msg_id = ((int(now) + self.time_offset) << 32) | (nanoseconds << 2)

        with self._msg_id_lock:
            if self._last_msg_id >= new_msg_id:
                new_msg_id = self._last_msg_id + 4

            self._last_msg_id = new_msg_id

        return new_msg_id

    def update_time_offset(self, correct_msg_id):
        """Updates the time offset based on a known correct message ID"""
        now = int(time.time())
        correct = correct_msg_id >> 32
        self.time_offset = correct - now

    # Entity processing

    def process_entities(self, tlo):
        """Processes all the found entities on the given TLObject,
           unless .enabled is False.

           Returns True if new input entities were added.
        """
        if not self.save_entities:
            return

        if not isinstance(tlo, TLObject) and hasattr(tlo, '__iter__'):
            # This may be a list of users already for instance
            entities = tlo
        else:
            entities = []
            if hasattr(tlo, 'chats') and hasattr(tlo.chats, '__iter__'):
                entities.extend(tlo.chats)
            if hasattr(tlo, 'users') and hasattr(tlo.users, '__iter__'):
                entities.extend(tlo.users)
            if not entities:
                return

        rows = []  # Rows to add (id, hash, username, phone, name)
        for e in entities:
            if not isinstance(e, TLObject):
                continue
            try:
                p = utils.get_input_peer(e, allow_self=False)
                marked_id = utils.get_peer_id(p)
            except ValueError:
                continue

            if isinstance(p, (InputPeerUser, InputPeerChannel)):
                if not p.access_hash:
                    # Some users and channels seem to be returned without
                    # an 'access_hash', meaning Telegram doesn't want you
                    # to access them. This is the reason behind ensuring
                    # that the 'access_hash' is non-zero. See issue #354.
                    # Note that this checks for zero or None, see #392.
                    continue
                else:
                    p_hash = p.access_hash
            elif isinstance(p, InputPeerChat):
                p_hash = 0
            else:
                continue

            username = getattr(e, 'username', None) or None
            if username is not None:
                username = username.lower()
            phone = getattr(e, 'phone', None)
            name = utils.get_display_name(e) or None
            rows.append((marked_id, p_hash, username, phone, name))
        if not rows:
            return

        with self._db_lock:
            self._cursor().executemany(
                'insert or replace into entities values (?,?,?,?,?)', rows
            )
            self.save()

    def get_input_entity(self, key):
        """Parses the given string, integer or TLObject key into a
           marked entity ID, which is then used to fetch the hash
           from the database.

           If a callable key is given, every row will be fetched,
           and passed as a tuple to a function, that should return
           a true-like value when the desired row is found.

           Raises ValueError if it cannot be found.
        """
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

        c = self._cursor()
        if isinstance(key, str):
            phone = utils.parse_phone(key)
            if phone:
                c.execute('select id, hash from entities where phone=?',
                          (phone,))
            else:
                username, _ = utils.parse_username(key)
                if username:
                    c.execute('select id, hash from entities where username=?',
                              (username,))

        if isinstance(key, int):
            c.execute('select id, hash from entities where id=?', (key,))

        result = c.fetchone()
        if not result and isinstance(key, str):
            # Try exact match by name if phone/username failed
            c.execute('select id, hash from entities where name=?', (key,))
            result = c.fetchone()

        c.close()
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

    # File processing

    def get_file(self, md5_digest, file_size, cls):
        tuple_ = self._cursor().execute(
            'select id, hash from sent_files '
            'where md5_digest = ? and file_size = ? and type = ?',
            (md5_digest, file_size, _SentFileType.from_type(cls).value)
        ).fetchone()
        if tuple_:
            # Both allowed classes have (id, access_hash) as parameters
            return cls(tuple_[0], tuple_[1])

    def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache %s instance' % type(instance))

        with self._db_lock:
            self._cursor().execute(
                'insert or replace into sent_files values (?,?,?,?,?)', (
                    md5_digest, file_size,
                    _SentFileType.from_type(type(instance)).value,
                    instance.id, instance.access_hash
            ))
            self.save()
