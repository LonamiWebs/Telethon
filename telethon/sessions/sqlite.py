import json
import os
import sqlite3
from base64 import b64decode
from os.path import isfile as file_exists
from threading import Lock, RLock

from .memory import MemorySession, _SentFileType
from ..crypto import AuthKey
from ..tl.types import (
    InputPhoto, InputDocument
)

EXTENSION = '.session'
CURRENT_VERSION = 3  # database version


class SQLiteSession(MemorySession):
    """This session contains the required information to login into your
       Telegram account. NEVER give the saved JSON file to anyone, since
       they would gain instant access to all your messages and contacts.

       If you think the session has been compromised, close all the sessions
       through an official Telegram client to revoke the authorization.
    """

    def __init__(self, session_id=None):
        super().__init__()
        """session_user_id should either be a string or another Session.
           Note that if another session is given, only parameters like
           those required to init a connection will be copied.
        """
        # These values will NOT be saved
        self.filename = ':memory:'
        self.save_entities = True

        if session_id:
            self.filename = session_id
            if not self.filename.endswith(EXTENSION):
                self.filename += EXTENSION

        # Cross-thread safety
        self._seq_no_lock = Lock()
        self._msg_id_lock = Lock()
        self._db_lock = RLock()

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

    def clone(self, to_instance=None):
        cloned = super().clone(to_instance)
        cloned.save_entities = self.save_entities
        return cloned

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
        super().set_dc(dc_id, server_address, port)
        self._update_session_table()

        # Fetch the auth_key corresponding to this data center
        c = self._cursor()
        c.execute('select auth_key from sessions')
        tuple_ = c.fetchone()
        if tuple_ and tuple_[0]:
            self._auth_key = AuthKey(data=tuple_[0])
        else:
            self._auth_key = None
        c.close()

    @MemorySession.auth_key.setter
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

    @classmethod
    def list_sessions(cls):
        """Lists all the sessions of the users who have ever connected
           using this client and never logged out
        """
        return [os.path.splitext(os.path.basename(f))[0]
                for f in os.listdir('.') if f.endswith(EXTENSION)]

    # Entity processing

    def process_entities(self, tlo):
        """Processes all the found entities on the given TLObject,
           unless .enabled is False.

           Returns True if new input entities were added.
        """
        if not self.save_entities:
            return

        rows = self._entities_to_rows(tlo)
        if not rows:
            return

        with self._db_lock:
            self._cursor().executemany(
                'insert or replace into entities values (?,?,?,?,?)', rows
            )
            self.save()

    def _fetchone_entity(self, query, args):
        c = self._cursor()
        c.execute(query, args)
        return c.fetchone()

    def get_entity_rows_by_phone(self, phone):
        return self._fetchone_entity(
            'select id, hash from entities where phone=?', (phone,))

    def get_entity_rows_by_username(self, username):
        return self._fetchone_entity(
            'select id, hash from entities where username=?', (username,))

    def get_entity_rows_by_name(self, name):
        return self._fetchone_entity(
            'select id, hash from entities where name=?', (name,))

    def get_entity_rows_by_id(self, id):
        return self._fetchone_entity(
            'select id, hash from entities where id=?', (id,))

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
