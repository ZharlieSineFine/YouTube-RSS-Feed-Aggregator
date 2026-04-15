"""Engine, session factory, and schema creation."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None

DEFAULT_SQLITE_URL = "sqlite:///data/aggregator.db"


def _normalize_postgres_url(url: str) -> str:
    """Use psycopg3 driver (installed as ``psycopg``); accepts generic ``postgresql://`` URLs."""
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def _postgres_url_from_env() -> str | None:
    """Build URL from ``POSTGRES_*`` when ``POSTGRES_HOST`` is set (e.g. Docker on localhost)."""
    host = (os.environ.get("POSTGRES_HOST") or "").strip()
    if not host:
        return None
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "ai_news_aggregator")
    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{db}"
    )


def get_database_url() -> str:
    """
    Resolve DB URL in order:

    1. ``DATABASE_URL`` if set (PostgreSQL URLs are normalized to ``postgresql+psycopg``;
       SQLite ``sqlite:///...`` is passed through).
    2. Else, if ``POSTGRES_HOST`` is set, build from ``POSTGRES_USER``, ``POSTGRES_PASSWORD``,
       ``POSTGRES_PORT``, ``POSTGRES_DB``.
    3. Else default SQLite file ``data/aggregator.db``.
    """
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if raw:
        return _normalize_postgres_url(raw)
    built = _postgres_url_from_env()
    if built:
        return built
    return DEFAULT_SQLITE_URL


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = get_database_url()
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "", 1)
            if not path.startswith(":") and path != "memory":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        connect_args: dict = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        kw: dict = {"echo": False, "future": True, "connect_args": connect_args}
        if not url.startswith("sqlite"):
            kw["pool_pre_ping"] = True
        _engine = create_engine(url, **kw)
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
        if "summary_zh" not in names:
            conn.execute(text("ALTER TABLE articles ADD COLUMN summary_zh TEXT"))
        if "summarized_at_zh" not in names:
            if is_sqlite:
                conn.execute(text("ALTER TABLE articles ADD COLUMN summarized_at_zh TEXT"))
            else:
                conn.execute(
                    text(
                        "ALTER TABLE articles ADD COLUMN summarized_at_zh TIMESTAMPTZ"
                    )
                )
        if "title_zh" not in names:
            conn.execute(text("ALTER TABLE articles ADD COLUMN title_zh TEXT"))


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
