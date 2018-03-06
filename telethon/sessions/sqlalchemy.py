try:
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy import Column, String, Integer, LargeBinary, orm
    import sqlalchemy as sql
except ImportError:
    sql = None
    pass

from ..crypto import AuthKey
from ..tl.types import InputPhoto, InputDocument

from .memory import MemorySession, _SentFileType

LATEST_VERSION = 1


class AlchemySessionContainer:
    def __init__(self, engine=None, session=None, table_prefix='',
                 table_base=None, manage_tables=True):
        if not sql:
            raise ImportError('SQLAlchemy not imported')
        if isinstance(engine, str):
            engine = sql.create_engine(engine)

        self.db_engine = engine
        if not session:
            db_factory = orm.sessionmaker(bind=self.db_engine)
            self.db = orm.scoping.scoped_session(db_factory)
        else:
            self.db = session

        table_base = table_base or declarative_base()
        (self.Version, self.Session, self.Entity,
         self.SentFile) = self.create_table_classes(self.db, table_prefix,
                                                    table_base)

        if manage_tables:
            table_base.metadata.bind = self.db_engine
            if not self.db_engine.dialect.has_table(self.db_engine,
                                                    self.Version.__tablename__):
                table_base.metadata.create_all()
                self.db.add(self.Version(version=LATEST_VERSION))
                self.db.commit()
            else:
                self.check_and_upgrade_database()

    @staticmethod
    def create_table_classes(db, prefix, Base):
        class Version(Base):
            query = db.query_property()
            __tablename__ = '{prefix}version'.format(prefix=prefix)
            version = Column(Integer, primary_key=True)

        class Session(Base):
            query = db.query_property()
            __tablename__ = '{prefix}sessions'.format(prefix=prefix)

            session_id = Column(String, primary_key=True)
            dc_id = Column(Integer, primary_key=True)
            server_address = Column(String)
            port = Column(Integer)
            auth_key = Column(LargeBinary)

        class Entity(Base):
            query = db.query_property()
            __tablename__ = '{prefix}entities'.format(prefix=prefix)

            session_id = Column(String, primary_key=True)
            id = Column(Integer, primary_key=True)
            hash = Column(Integer, nullable=False)
            username = Column(String)
            phone = Column(Integer)
            name = Column(String)

        class SentFile(Base):
            query = db.query_property()
            __tablename__ = '{prefix}sent_files'.format(prefix=prefix)

            session_id = Column(String, primary_key=True)
            md5_digest = Column(LargeBinary, primary_key=True)
            file_size = Column(Integer, primary_key=True)
            type = Column(Integer, primary_key=True)
            id = Column(Integer)
            hash = Column(Integer)

        return Version, Session, Entity, SentFile

    def check_and_upgrade_database(self):
        row = self.Version.query.all()
        version = row[0].version if row else 1
        if version == LATEST_VERSION:
            return

        self.Version.query.delete()

        # Implement table schema updates here and increase version

        self.db.add(self.Version(version=version))
        self.db.commit()

    def new_session(self, session_id):
        return AlchemySession(self, session_id)

    def list_sessions(self):
        return

    def save(self):
        self.db.commit()


class AlchemySession(MemorySession):
    def __init__(self, container, session_id):
        super().__init__()
        self.container = container
        self.db = container.db
        self.Version, self.Session, self.Entity, self.SentFile = (
            container.Version, container.Session, container.Entity,
            container.SentFile)
        self.session_id = session_id
        self._load_session()

    def _load_session(self):
        sessions = self._db_query(self.Session).all()
        session = sessions[0] if sessions else None
        if session:
            self._dc_id = session.dc_id
            self._server_address = session.server_address
            self._port = session.port
            self._auth_key = AuthKey(data=session.auth_key)

    def clone(self, to_instance=None):
        return super().clone(MemorySession())

    def set_dc(self, dc_id, server_address, port):
        super().set_dc(dc_id, server_address, port)
        self._update_session_table()

        sessions = self._db_query(self.Session).all()
        session = sessions[0] if sessions else None
        if session and session.auth_key:
            self._auth_key = AuthKey(data=session.auth_key)
        else:
            self._auth_key = None

    @MemorySession.auth_key.setter
    def auth_key(self, value):
        self._auth_key = value
        self._update_session_table()

    def _update_session_table(self):
        self.Session.query.filter(
            self.Session.session_id == self.session_id).delete()
        new = self.Session(session_id=self.session_id, dc_id=self._dc_id,
                           server_address=self._server_address,
                           port=self._port,
                           auth_key=(self._auth_key.key
                                     if self._auth_key else b''))
        self.db.merge(new)

    def _db_query(self, dbclass, *args):
        return dbclass.query.filter(dbclass.session_id == self.session_id,
                                    *args)

    def save(self):
        self.container.save()

    def close(self):
        # Nothing to do here, connection is managed by AlchemySessionContainer.
        pass

    def delete(self):
        self._db_query(self.Session).delete()
        self._db_query(self.Entity).delete()
        self._db_query(self.SentFile).delete()

    def _entity_values_to_row(self, id, hash, username, phone, name):
        return self.Entity(session_id=self.session_id, id=id, hash=hash,
                           username=username, phone=phone, name=name)

    def process_entities(self, tlo):
        rows = self._entities_to_rows(tlo)
        if not rows:
            return

        for row in rows:
            self.db.merge(row)
        self.save()

    def get_entity_rows_by_phone(self, key):
        row = self._db_query(self.Entity,
                             self.Entity.phone == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_username(self, key):
        row = self._db_query(self.Entity,
                             self.Entity.username == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_name(self, key):
        row = self._db_query(self.Entity,
                             self.Entity.name == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_id(self, key):
        row = self._db_query(self.Entity, self.Entity.id == key).one_or_none()
        return row.id, row.hash if row else None

    def get_file(self, md5_digest, file_size, cls):
        row = self._db_query(self.SentFile,
                             self.SentFile.md5_digest == md5_digest,
                             self.SentFile.file_size == file_size,
                             self.SentFile.type == _SentFileType.from_type(
                                 cls).value).one_or_none()
        return row.id, row.hash if row else None

    def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache %s instance' % type(instance))

        self.db.merge(
            self.SentFile(session_id=self.session_id, md5_digest=md5_digest,
                          type=_SentFileType.from_type(type(instance)).value,
                          id=instance.id, hash=instance.access_hash))
        self.save()
