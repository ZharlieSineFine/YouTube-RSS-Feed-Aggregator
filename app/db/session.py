"""Engine, session factory, and schema creation."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

DEFAULT_SQLITE_URL = "sqlite:///data/aggregator.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URL)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_database_url()
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            if not path.startswith(":") and path != "memory":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, echo=False, future=True, connect_args=connect_args)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


def _migrate_article_summary_columns(engine: Engine) -> None:
    """Add agent columns to existing DBs (create_all does not alter tables)."""
    insp = inspect(engine)
    if not insp.has_table("articles"):
        return
    names = {c["name"] for c in insp.get_columns("articles")}
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        if "summary" not in names:
            conn.execute(text("ALTER TABLE articles ADD COLUMN summary TEXT"))
        if "summarized_at" not in names:
            if is_sqlite:
                conn.execute(text("ALTER TABLE articles ADD COLUMN summarized_at TEXT"))
            else:
                conn.execute(
                    text(
                        "ALTER TABLE articles ADD COLUMN summarized_at TIMESTAMPTZ"
                    )
                )


def init_db() -> None:
    """Create tables if they do not exist; apply lightweight migrations."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _migrate_article_summary_columns(engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional session context manager."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
