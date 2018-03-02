from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, Blob, orm
import sqlalchemy as sql

from ..tl.types import InputPhoto, InputDocument

from .memory import MemorySession, _SentFileType

Base = declarative_base()
LATEST_VERSION = 1


class DBVersion(Base):
    __tablename__ = "version"
    version = Column(Integer, primary_key=True)


class DBSession(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    dc_id = Column(Integer, primary_key=True)
    server_address = Column(String)
    port = Column(Integer)
    auth_key = Column(Blob)


class DBEntity(Base):
    __tablename__ = "entities"

    session_id = Column(String, primary_key=True)
    id = Column(Integer, primary_key=True)
    hash = Column(Integer, nullable=False)
    username = Column(String)
    phone = Column(Integer)
    name = Column(String)


class DBSentFile(Base):
    __tablename__ = "sent_files"

    session_id = Column(String, primary_key=True)
    md5_digest = Column(Blob, primary_key=True)
    file_size = Column(Integer, primary_key=True)
    type = Column(Integer, primary_key=True)
    id = Column(Integer)
    hash = Column(Integer)


class AlchemySessionContainer:
    def __init__(self, database):
        if isinstance(database, str):
            database = sql.create_engine(database)

        self.db_engine = database
        db_factory = orm.sessionmaker(bind=self.db_engine)
        self.db = orm.scoping.scoped_session(db_factory)

        if not self.db_engine.dialect.has_table(self.db_engine,
                                                DBVersion.__tablename__):
            Base.metadata.create_all(bind=self.db_engine)
            self.db.add(DBVersion(version=LATEST_VERSION))
            self.db.commit()
        else:
            self.check_and_upgrade_database()

        DBVersion.query = self.db.query_property()
        DBSession.query = self.db.query_property()
        DBEntity.query = self.db.query_property()
        DBSentFile.query = self.db.query_property()

    def check_and_upgrade_database(self):
        row = DBVersion.query.get()
        version = row.version if row else 1
        if version == LATEST_VERSION:
            return

        DBVersion.query.delete()

        # Implement table schema updates here and increase version

        self.db.add(DBVersion(version=version))
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
        self.session_id = session_id

    def clone(self, to_instance=None):
        cloned = to_instance or self.__class__(self.container, self.session_id)
        return super().clone(cloned)

    def set_dc(self, dc_id, server_address, port):
        super().set_dc(dc_id, server_address, port)

    def _update_session_table(self):
        self.db.query(DBSession).filter(
            DBSession.session_id == self.session_id).delete()
        new = DBSession(session_id=self.session_id, dc_id=self._dc_id,
                        server_address=self._server_address, port=self._port,
                        auth_key=self._auth_key.key if self._auth_key else b'')
        self.db.merge(new)

    def _db_query(self, dbclass, *args):
        return self.db.query(dbclass).filter(
            dbclass.session_id == self.session_id,
            *args)

    def save(self):
        self.container.save()

    def close(self):
        # Nothing to do here, connection is managed by AlchemySessionContainer.
        pass

    def delete(self):
        self._db_query(DBSession).delete()
        self._db_query(DBEntity).delete()
        self._db_query(DBSentFile).delete()

    def _entity_values_to_row(self, id, hash, username, phone, name):
        return DBEntity(session_id=self.session_id, id=id, hash=hash,
                        username=username, phone=phone, name=name)

    def process_entities(self, tlo):
        rows = self._entities_to_rows(tlo)
        if not rows:
            return

        self.db.add_all(rows)
        self.save()

    def get_entity_rows_by_phone(self, key):
        row = self._db_query(DBEntity, DBEntity.phone == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_username(self, key):
        row = self._db_query(DBEntity, DBEntity.username == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_name(self, key):
        row = self._db_query(DBEntity, DBEntity.name == key).one_or_none()
        return row.id, row.hash if row else None

    def get_entity_rows_by_id(self, key):
        row = self._db_query(DBEntity, DBEntity.id == key).one_or_none()
        return row.id, row.hash if row else None

    def get_file(self, md5_digest, file_size, cls):
        row = self._db_query(DBSentFile, DBSentFile.md5_digest == md5_digest,
                             DBSentFile.file_size == file_size,
                             DBSentFile.type == _SentFileType.from_type(
                                 cls).value).one_or_none()
        return row.id, row.hash if row else None

    def cache_file(self, md5_digest, file_size, instance):
        if not isinstance(instance, (InputDocument, InputPhoto)):
            raise TypeError('Cannot cache %s instance' % type(instance))

        self.db.merge(
            DBSentFile(session_id=self.session_id, md5_digest=md5_digest,
                       type=_SentFileType.from_type(type(instance)).value,
                       id=instance.id, hash=instance.access_hash))
        self.save()
