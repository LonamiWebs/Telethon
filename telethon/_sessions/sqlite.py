import datetime
import os
import time
import ipaddress
from typing import Optional, List

from .abstract import Session
from .._misc import utils
from .. import _tl
from .types import DataCenter, ChannelState, SessionState, Entity

try:
    import sqlite3
    sqlite3_err = None
except ImportError as e:
    sqlite3 = None
    sqlite3_err = type(e)

EXTENSION = '.session'
CURRENT_VERSION = 8  # database version


class SQLiteSession(Session):
    """
    This session contains the required information to login into your
    Telegram account. NEVER give the saved session file to anyone, since
    they would gain instant access to all your messages and contacts.

    If you think the session has been compromised, close all the sessions
    through an official Telegram client to revoke the authorization.
    """

    def __init__(self, session_id=None):
        if sqlite3 is None:
            raise sqlite3_err

        super().__init__()
        self.filename = ':memory:'
        self.save_entities = True

        if session_id:
            self.filename = os.fspath(session_id)
            if not self.filename.endswith(EXTENSION):
                self.filename += EXTENSION

        self._conn = None
        c = self._cursor()
        c.execute("select name from sqlite_master "
                  "where type='table' and name='version'")
        if c.fetchone():
            # Tables already exist, check for the version
            c.execute("select version from version")
            version = c.fetchone()[0]
            if version < CURRENT_VERSION:
                self._upgrade_database(old=version)
                c.execute("delete from version")
                c.execute("insert into version values (?)", (CURRENT_VERSION,))
                self._conn.commit()
        else:
            # Tables don't exist, create new ones
            self._create_table(c, 'version (version integer primary key)')
            self._mk_tables(c)
            c.execute("insert into version values (?)", (CURRENT_VERSION,))
            self._conn.commit()

        # Must have committed or else the version will not have been updated while new tables
        # exist, leading to a half-upgraded state.
        c.close()

    def _upgrade_database(self, old):
        c = self._cursor()
        if old == 1:
            old += 1
            # old == 1 doesn't have the old sent_files so no need to drop
        if old == 2:
            old += 1
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
        if old == 3:
            old += 1
            self._create_table(c, """update_state (
                id integer primary key,
                pts integer,
                qts integer,
                date integer,
                seq integer
            )""")
        if old == 4:
            old += 1
            c.execute("alter table sessions add column takeout_id integer")
        if old == 5:
            # Not really any schema upgrade, but potentially all access
            # hashes for User and Channel are wrong, so drop them off.
            old += 1
            c.execute('delete from entities')
        if old == 6:
            old += 1
            c.execute("alter table entities add column date integer")
        if old == 7:
            self._mk_tables(c)
            c.execute('''
                insert into datacenter (id, ipv4, ipv6, port, auth)
                select dc_id, server_address, server_address, port, auth_key
                from sessions
            ''')
            c.execute('''
                insert into session (user_id, dc_id, bot, pts, qts, date, seq, takeout_id)
                select
                    0,
                    s.dc_id,
                    0,
                    coalesce(u.pts, 0),
                    coalesce(u.qts, 0),
                    coalesce(u.date, 0),
                    coalesce(u.seq, 0),
                    s.takeout_id
                from sessions s
                left join update_state u on u.id = 0
                limit 1
            ''')
            c.execute('''
                insert into entity (id, hash, ty)
                select
                    case
                        when id < -1000000000000 then -(id + 1000000000000)
                        when id < 0 then -id
                        else id
                    end,
                    hash,
                    case
                        when id < -1000000000000 then 67
                        when id < 0 then 71
                        else 85
                    end
                from entities
            ''')
            c.execute('drop table sessions')
            c.execute('drop table entities')
            c.execute('drop table sent_files')
            c.execute('drop table update_state')

    def _mk_tables(self, c):
        self._create_table(
            c,
            '''datacenter (
                id integer primary key,
                ipv4 text not null,
                ipv6 text,
                port integer not null,
                auth blob not null
            )''',
            '''session (
                user_id integer primary key,
                dc_id integer not null,
                bot integer not null,
                pts integer not null,
                qts integer not null,
                date integer not null,
                seq integer not null,
                takeout_id integer
            )''',
            '''channel (
                channel_id integer primary key,
                pts integer not null
            )''',
            '''entity (
                id integer primary key,
                hash integer not null,
                ty integer not null
            )''',
        )

    async def insert_dc(self, dc: DataCenter):
        self._execute(
            'insert or replace into datacenter values (?,?,?,?,?)',
            dc.id,
            str(ipaddress.ip_address(dc.ipv4)),
            str(ipaddress.ip_address(dc.ipv6)) if dc.ipv6 else None,
            dc.port,
            dc.auth
        )

    async def get_all_dc(self) -> List[DataCenter]:
        c = self._cursor()
        res = []
        for (id, ipv4, ipv6, port, auth) in c.execute('select * from datacenter'):
            res.append(DataCenter(
                id=id,
                ipv4=int(ipaddress.ip_address(ipv4)),
                ipv6=int(ipaddress.ip_address(ipv6)) if ipv6 else None,
                port=port,
                auth=auth,
            ))
        return res

    async def set_state(self, state: SessionState):
        c = self._cursor()
        try:
            self._execute('delete from session')
            self._execute(
                'insert into session values (?,?,?,?,?,?,?,?)',
                state.user_id,
                state.dc_id,
                int(state.bot),
                state.pts,
                state.qts,
                state.date,
                state.seq,
                state.takeout_id,
            )
        finally:
            c.close()

    async def get_state(self) -> Optional[SessionState]:
        row = self._execute('select * from session')
        return SessionState(*row) if row else None

    async def insert_channel_state(self, state: ChannelState):
        self._execute(
            'insert or replace into channel values (?,?)',
            state.channel_id,
            state.pts,
        )

    async def get_all_channel_states(self) -> List[ChannelState]:
        c = self._cursor()
        try:
            return [
                ChannelState(*row)
                for row in c.execute('select * from channel')
            ]
        finally:
            c.close()

    async def insert_entities(self, entities: List[Entity]):
        c = self._cursor()
        try:
            c.executemany(
                'insert or replace into entity values (?,?,?)',
                [(e.id, e.hash, e.ty) for e in entities]
            )
        finally:
            c.close()

    async def get_entity(self, ty: Optional[int], id: int) -> Optional[Entity]:
        row = self._execute('select ty, id, hash from entity where id = ?', id)
        return Entity(*row) if row else None

    async def save(self):
        # This is a no-op if there are no changes to commit, so there's
        # no need for us to keep track of an "unsaved changes" variable.
        if self._conn is not None:
            self._conn.commit()

    @staticmethod
    def _create_table(c, *definitions):
        for definition in definitions:
            c.execute('create table {}'.format(definition))

    def _cursor(self):
        """Asserts that the connection is open and returns a cursor"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.filename,
                                         check_same_thread=False)
        return self._conn.cursor()

    def _execute(self, stmt, *values):
        """
        Gets a cursor, executes `stmt` and closes the cursor,
        fetching one row afterwards and returning its result.
        """
        c = self._cursor()
        try:
            return c.execute(stmt, values).fetchone()
        finally:
            c.close()
