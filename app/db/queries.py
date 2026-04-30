"""Read helpers for inspection, debugging, and downstream features."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Set

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
                    "title_zh": art.title_zh,
                    "url": art.url,
                    "published_at": art.published_at,
                    "source_kind": src.kind,
                    "source_label": src.label,
                    "content_chars": len(art.content) if art.content else 0,
                    "has_summary": bool(art.summary),
                    "summary_chars": len(art.summary) if art.summary else 0,
                    "summary": art.summary,
                    "summarized_at": art.summarized_at,
                    "has_summary_zh": bool(art.summary_zh),
                    "summary_zh": art.summary_zh,
                    "summarized_at_zh": art.summarized_at_zh,
                }
            )
        return out


def youtube_video_ids_in_db(session: Session) -> Set[str]:
    """
    YouTube video IDs we already have rows for (from ``extra_json`` or parsed ``url``).

    Used to avoid missing late-appearing RSS items whose ``published_at`` is before
    the per-channel incremental watermark.
    """
    ids: set[str] = set()
    stmt = (
        select(Article.url, Article.extra_json)
        .join(Source, Article.source_id == Source.id)
        .where(Source.kind == "youtube")
    )
    for url, extra in session.execute(stmt).all():
        vid: str | None = None
        if extra:
            try:
                d = json.loads(extra)
                v = d.get("video_id")
                if isinstance(v, str) and len(v) == 11:
                    vid = v
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        if not vid and url:
            m = re.search(r"(?:[?&]v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
            if m:
                vid = m.group(1)
        if vid:
            ids.add(vid)
    return ids
