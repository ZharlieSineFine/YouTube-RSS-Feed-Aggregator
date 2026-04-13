"""Generate per-article summaries via OpenAI and persist to the database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import select

from app.db.models import Article
from app.db.session import init_db, session_scope

from .config import AGENT_LLM_BACKEND, MAX_INPUT_CHARS, chat_model_name
from .llm_client import get_chat_client
from .system_prompt import DEFAULT_SYSTEM_PROMPT


def _truncate_body(text: str, max_chars: int) -> Tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n\n[Truncated for summarization.]", True


def _build_user_message(article: Article) -> str:
    body = article.content or ""
    body, truncated = _truncate_body(body, MAX_INPUT_CHARS)
    pub = article.published_at
    pub_s = pub.isoformat() if pub else "unknown"
    lines = [
        f"Title: {article.title}",
        f"URL: {article.url}",
        f"Published: {pub_s}",
    ]
    if truncated:
        lines.append("Note: body was truncated due to length.")
    lines.append("")
    lines.append("Body:")
    lines.append(body)
    return "\n".join(lines)


def summarize_text(
    client,
    *,
    system_prompt: str,
    user_message: str,
    model: str | None = None,
) -> str:
    model = model or chat_model_name()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )
    choice = resp.choices[0].message.content
    if not choice or not choice.strip():
        raise RuntimeError("LLM returned an empty summary.")
    return choice.strip()


def summarize_pending(
    *,
    limit: int = 10,
    summarize_all: bool = False,
    force: bool = False,
    dry_run: bool = False,
    system_prompt: str | None = None,
) -> int:
    """
    Summarize articles (newest first). Skips rows with no content.

    If ``summarize_all`` is True, every candidate with ``summary`` empty (unless
    ``force``) is processed; ``limit`` is ignored.

    Returns the number of articles updated.
    """
    init_db()
    sp = system_prompt or DEFAULT_SYSTEM_PROMPT
    if summarize_all:
        pending_ids = _select_all_candidate_ids(force=force)
    else:
        pending_ids = _select_candidate_ids(limit=limit, force=force)

    if dry_run:
        label = "all pending" if summarize_all else f"up to {limit}"
        print(f"Would summarize {len(pending_ids)} article(s) ({label}, dry run).")
        with session_scope() as session:
            for aid in pending_ids:
                a = session.get(Article, aid)
                if a:
                    print(f"  id={a.id} title={a.title[:80]!r}")
        return 0

    client = get_chat_client()
    model_label = chat_model_name()
    if AGENT_LLM_BACKEND == "ollama":
        print(f"LLM: Ollama  model={model_label!r}")
    else:
        print(f"LLM: OpenAI-compatible  model={model_label!r}")
    if summarize_all:
        print("Mode: summarize all pending articles with content.")

    done = 0
    if not pending_ids:
        print("No articles to summarize (need content, and summary empty unless --force).")
        return 0

    for aid in pending_ids:
        with session_scope() as session:
            article = session.get(Article, aid)
            if article is None:
                continue
            if not (article.content and article.content.strip()):
                continue
            user_msg = _build_user_message(article)
            text = summarize_text(client, system_prompt=sp, user_message=user_msg)
            article.summary = text
            article.summarized_at = datetime.now(timezone.utc)
            done += 1
            print(f"Summarized id={article.id} ({len(text)} chars summary)")

    return done


def _base_candidate_query(force: bool):
    q = (
        select(Article.id)
        .where(Article.content.isnot(None))
        .where(Article.content != "")
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    )
    if not force:
        q = q.where(Article.summary.is_(None))
    return q


def _select_candidate_ids(limit: int, force: bool) -> list[int]:
    lim = max(1, min(limit, 500))
    with session_scope() as session:
        q = _base_candidate_query(force).limit(lim)
        return list(session.scalars(q).all())


def _select_all_candidate_ids(force: bool) -> list[int]:
    with session_scope() as session:
        q = _base_candidate_query(force)
        return list(session.scalars(q).all())
