"""Database layer: SQLAlchemy models and persistence for ingested content."""

from .models import Article, Base, Source
from .queries import db_stats, recent_articles
from .session import get_database_url, get_engine, init_db, session_scope
from .store import persist_ingest_results

__all__ = [
    "Article",
    "Base",
    "Source",
    "db_stats",
    "get_database_url",
    "get_engine",
    "init_db",
    "persist_ingest_results",
    "recent_articles",
    "session_scope",
]
