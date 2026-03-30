from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine as sa_create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from config.settings import settings

_engine: Engine | None = None
_SessionFactory = None


def create_engine() -> Engine:
    return sa_create_engine(
        settings.DB_URL,
        poolclass=QueuePool,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def get_engine() -> Engine:
    global _engine, _SessionFactory
    if _engine is None:
        _engine = create_engine()
        _SessionFactory = sessionmaker(bind=_engine)
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    engine = get_engine()
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_connection() -> tuple[bool, str]:
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user, version()"))
            row = result.fetchone()
            db_name, user, version = row[0], row[1], row[2].split(" ")[0] + " " + row[2].split(" ")[1]
            return True, f"Connected to {db_name} as {user} ({version})"
    except Exception as e:
        return False, str(e)


def reset_engine() -> None:
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
