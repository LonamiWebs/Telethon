import sqlite3
from pathlib import Path
from typing import Optional, Union

from ..session import ChannelState, DataCenter, Session, UpdateState, User
from .storage import Storage

EXTENSION = ".session"
CURRENT_VERSION = 10


class SqliteSession(Storage):
    """
    Session storage backed by SQLite.

    SQLite is a reliable way to persist data to disk and offers file locking.

    Paths without extension will have ``'.session'`` appended to them.
    This is by convention, and to make it harder to commit session files to
    an VCS by accident (adding ``*.session`` to ``.gitignore`` will catch them).
    """

    def __init__(self, file: Union[str, Path]):
        path = Path(file)
        if not path.suffix:
            path = path.with_suffix(EXTENSION)

        self._path = path
        self._conn: Optional[sqlite3.Connection] = None

    async def load(self) -> Optional[Session]:
        conn = self._current_conn()

        c = conn.cursor()
        with conn:
            version = self._get_or_init_version(c)
            if version < CURRENT_VERSION:
                if version == 7:
                    session = self._load_v7(c)
                else:
                    raise ValueError(
                        "only migration from sqlite session format 7 supported"
                    )

                self._reset(c)
                self._get_or_init_version(c)
                self._save_v10(c, session)

            return self._load_v10(c)

    async def save(self, session: Session) -> None:
        conn = self._current_conn()
        with conn:
            self._save_v10(conn.cursor(), session)
        conn.close()
        self._conn = None

    async def delete(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        self._path.unlink()

    def _current_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._path)

        return self._conn

    @staticmethod
    def _load_v7(c: sqlite3.Cursor) -> Session:
        # Session v7 format from telethon v1
        c.execute("select dc_id, server_address, port, auth_key from sessions")
        sessions = c.fetchall()
        c.execute("select pts, qts, date, seq from update_state where id = 0")
        state = c.fetchone()
        c.execute("select id, pts from update_state where id != 0")
        channelstate = c.fetchall()

        return Session(
            dcs=[
                DataCenter(id=id, addr=f"{ip}:{port}", auth=auth)
                for (id, ip, port, auth) in sessions
            ],
            user=None,
            state=UpdateState(
                pts=state[0],
                qts=state[1],
                date=state[2],
                seq=state[3],
                channels=[ChannelState(id=id, pts=pts) for id, pts in channelstate],
            ),
        )

    @staticmethod
    def _load_v10(c: sqlite3.Cursor) -> Session:
        c.execute("select * from datacenter")
        datacenter = c.fetchall()
        c.execute("select * from user")
        user = c.fetchone()
        c.execute("select * from state")
        state = c.fetchone()
        c.execute("select * from channelstate")
        channelstate = c.fetchall()

        return Session(
            dcs=[
                DataCenter(id=id, addr=addr, auth=auth)
                for (id, addr, auth) in datacenter
            ],
            user=User(id=user[0], dc=user[1], bot=bool(user[2]), username=user[3])
            if user
            else None,
            state=UpdateState(
                pts=state[0],
                qts=state[1],
                date=state[2],
                seq=state[3],
                channels=[ChannelState(id=id, pts=pts) for id, pts in channelstate],
            )
            if state
            else None,
        )

    @staticmethod
    def _save_v10(c: sqlite3.Cursor, session: Session) -> None:
        c.execute("delete from datacenter")
        c.execute("delete from user")
        c.execute("delete from state")
        c.execute("delete from channelstate")
        c.executemany(
            "insert into datacenter values (?, ?, ?)",
            [(dc.id, dc.addr, dc.auth) for dc in session.dcs],
        )
        if user := session.user:
            c.execute(
                "insert into user values (?, ?, ?)", (user.id, user.dc, int(user.bot))
            )
        if state := session.state:
            c.execute(
                "insert into state values (?, ?, ?, ?)",
                (state.pts, state.qts, state.date, state.seq),
            )
            c.executemany(
                "insert into channelstate values (?, ?)",
                [(channel.id, channel.pts) for channel in state.channels],
            )

    @staticmethod
    def _reset(c: sqlite3.Cursor) -> None:
        safe_chars = "_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

        c.execute("select name from sqlite_master where type='table'")
        for (name,) in c.fetchall():
            # Can't format arguments for table names. Regardless, it shouldn't
            # be an SQL-injection because names come from `sqlite_master`.
            # Just to be on the safe-side, check for r'\w+' nevertheless,
            # avoiding referencing globals which could've been monkey-patched.
            for char in name:
                if char not in safe_chars or name.__len__() > 20:
                    raise ValueError(f"potentially unsafe table name: {name}")

            c.execute(f"drop table {name}")

    @staticmethod
    def _get_or_init_version(c: sqlite3.Cursor) -> int:
        c.execute(
            "select name from sqlite_master where type='table' and name='version'"
        )
        if c.fetchone():
            c.execute("select version from version")
            tup = c.fetchone()
            if tup and isinstance(tup[0], int):
                return tup[0]
            SqliteSession._reset(c)

        SqliteSession._create_tables(c)
        c.execute("insert into version values (?)", (CURRENT_VERSION,))
        return CURRENT_VERSION

    @staticmethod
    def _create_tables(c: sqlite3.Cursor) -> None:
        c.executescript(
            """
            create table version (
                version integer primary key
            );
            create table datacenter(
                id integer primary key,
                addr text not null,
                auth blob
            );
            create table user(
                id integer primary key,
                dc integer not null,
                bot integer not null
            );
            create table state(
                pts integer not null,
                qts integer not null,
                date integer not null,
                seq integer not null
            );
            create table channelstate(
                id integer primary key,
                pts integer not null
            );
            """
        )
