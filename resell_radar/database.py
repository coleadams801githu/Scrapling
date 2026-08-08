"""Database engine and session factory for Resell Radar."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from resell_radar.models import Base

_DEFAULT_DB_URL = "sqlite:///resell_radar.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DB_URL)


def create_db_engine(database_url: str | None = None):
    url = database_url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, echo=False)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def init_db(database_url: str | None = None) -> None:
    """Create all tables if they do not exist."""
    global _engine, _SessionLocal
    _engine = create_db_engine(database_url)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=_engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that yields a database session and commits/rolls back on exit."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
