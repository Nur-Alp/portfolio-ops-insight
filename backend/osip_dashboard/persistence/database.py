"""Engine and session construction."""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


def create_database_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    # SQLite's default journal mode gives writers and readers exclusive
    # access to the whole file, so a write transaction from one request
    # (e.g. reconcile_fund() during a publish) can make an unrelated request
    # a few hundred milliseconds later fail immediately with "database is
    # locked" instead of just waiting. WAL mode lets readers proceed
    # concurrently with a writer, and busy_timeout makes any real remaining
    # contention retry for a few seconds instead of failing on first contact.
    connect_args = {"timeout": 30} if is_sqlite else {}
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
    return engine


def create_session_factory(engine: Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

