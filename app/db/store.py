"""Persist scraper results into the database."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, Source
from .session import init_db, session_scope


def _get_or_create_source(
    session: Session, kind: str, external_ref: str, label: str
) -> Source:
    q = select(Source).where(Source.kind == kind, Source.external_ref == external_ref)
    found = session.scalars(q).first()
    if found:
        return found
    row = Source(kind=kind, external_ref=external_ref, label=label)
    session.add(row)
    session.flush()
    return row


def _upsert_article(
    session: Session,
    source: Source,
    title: str,
    url: str,
    published_at: Optional[datetime],
    content: Optional[str],
    extra: Optional[dict],
) -> bool:
    """Return True if a new row was inserted."""
    q = select(Article).where(Article.url == url)
    existing = session.scalars(q).first()
    extra_s = json.dumps(extra, ensure_ascii=False) if extra else None
    if existing:
        if title and title != existing.title:
            existing.title = title
        if published_at is not None and existing.published_at != published_at:
            existing.published_at = published_at
        if content and (existing.content is None or len(content) > len(existing.content or "")):
            existing.content = content
        if extra_s and extra_s != (existing.extra_json or ""):
            existing.extra_json = extra_s
        return False
    session.add(
        Article(
            source_id=source.id,
            title=title[:1024],
            url=url[:2048],
            published_at=published_at,
            content=content,
            extra_json=extra_s,
        )
    )
    return True


def persist_ingest_results(results: Dict[str, List[Any]]) -> int:
    """
    Upsert all items from a run_all() result dict into the database.

    Returns the number of newly inserted rows (not updated).
    """
    init_db()
    inserted = 0
    with session_scope() as session:
        for video in results.get("youtube") or []:
            src = _get_or_create_source(
                session,
                "youtube",
                video.channel_id,
                f"YouTube {video.channel_id}",
            )
            extra = {"video_id": video.video_id, "channel_id": video.channel_id}
            if _upsert_article(
                session,
                src,
                video.title,
                video.url,
                video.published_at,
                video.transcript,
                extra,
            ):
                inserted += 1

        src_a = _get_or_create_source(session, "anthropic", "default", "Anthropic RSS")
        for article in results.get("anthropic") or []:
            ft = getattr(article.feed_type, "value", None) or str(article.feed_type)
            extra = {
                "guid": article.guid,
                "feed_type": ft,
                "category": article.category or "",
            }
            if _upsert_article(
                session,
                src_a,
                article.title,
                article.url,
                article.published_at,
                article.content,
                extra,
            ):
                inserted += 1

        src_o = _get_or_create_source(session, "openai", "default", "OpenAI News")
        for article in results.get("openai") or []:
            extra = {"description": (article.description or "")[:2000]}
            if _upsert_article(
                session,
                src_o,
                article.title,
                article.url,
                article.published_at,
                article.content,
                extra,
            ):
                inserted += 1

    return inserted
