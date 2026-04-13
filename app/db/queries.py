"""Read helpers for inspection, debugging, and downstream features."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Article, Source
from .session import init_db, session_scope


def db_stats(session: Session | None = None) -> Dict[str, int]:
    """Return row counts for ``sources`` and ``articles``."""
    if session is not None:
        n_src = session.scalar(select(func.count()).select_from(Source)) or 0
        n_art = session.scalar(select(func.count()).select_from(Article)) or 0
        return {"sources": int(n_src), "articles": int(n_art)}
    init_db()
    with session_scope() as s:
        return db_stats(s)


def recent_articles(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Latest articles by ``published_at`` (then ``id``), with source metadata.

    ``limit`` is capped for safety when used from CLIs.
    """
    lim = max(1, min(int(limit), 500))
    init_db()
    with session_scope() as s:
        stmt = (
            select(Article, Source)
            .join(Source, Article.source_id == Source.id)
            .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
            .limit(lim)
        )
        rows = s.execute(stmt).all()
        out: List[Dict[str, Any]] = []
        for art, src in rows:
            out.append(
                {
                    "id": art.id,
                    "title": art.title,
                    "url": art.url,
                    "published_at": art.published_at,
                    "source_kind": src.kind,
                    "source_label": src.label,
                    "content_chars": len(art.content) if art.content else 0,
                    "has_summary": bool(art.summary),
                    "summary_chars": len(art.summary) if art.summary else 0,
                    "summary": art.summary,
                    "summarized_at": art.summarized_at,
                }
            )
        return out
