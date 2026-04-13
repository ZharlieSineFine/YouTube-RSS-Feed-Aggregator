"""Generate per-article summaries via OpenAI and persist to the database."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from sqlalchemy import or_, select

from app.db.models import Article
from app.db.session import init_db, session_scope

from .config import AGENT_LLM_BACKEND, MAX_INPUT_CHARS, agent_summary_languages, chat_model_name
from .llm_client import get_chat_client
from .system_prompt import get_effective_system_prompt_for_language


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


def _lang_filled(article: Article, lang: str) -> bool:
    if lang == "en":
        return bool(article.summary and article.summary.strip())
    if lang == "zh-cn":
        return bool(article.summary_zh and article.summary_zh.strip())
    return bool(article.summary and article.summary.strip())


def _parse_zh_model_output(raw: str) -> tuple[str | None, str]:
    """
    First line ``TITLE_ZH: …`` (case-insensitive prefix) → stored title translation + body.
    If missing, body is full text and title translation is None.
    """
    text = raw.strip()
    if not text:
        return None, ""
    lines = text.splitlines()
    first = lines[0].strip()
    key = "title_zh:"
    if first.lower().startswith(key):
        title_zh = first[len(key) :].strip() or None
        body = "\n".join(lines[1:]).strip()
        return title_zh, body
    return None, text


def _apply_summary(article: Article, lang: str, text: str, now: datetime) -> None:
    if lang == "en":
        article.summary = text
        article.summarized_at = now
    elif lang == "zh-cn":
        title_zh, body = _parse_zh_model_output(text)
        article.summary_zh = body
        article.summarized_at_zh = now
        if title_zh:
            article.title_zh = title_zh
    else:
        article.summary = text
        article.summarized_at = now


def _missing_lang_sql_filter(langs: list[str]):
    """Rows that still need at least one configured language (when not using --force)."""
    parts = []
    if "en" in langs:
        parts.append(or_(Article.summary.is_(None), Article.summary == ""))
    if "zh-cn" in langs:
        parts.append(or_(Article.summary_zh.is_(None), Article.summary_zh == ""))
    for lang in langs:
        if lang not in ("en", "zh-cn"):
            parts.append(or_(Article.summary.is_(None), Article.summary == ""))
    if not parts:
        parts.append(Article.summary.is_(None))
    return or_(*parts) if len(parts) > 1 else parts[0]


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

    Uses ``AGENT_SUMMARY_LANGUAGES`` (e.g. ``en,zh-cn``) to fill ``summary`` and/or ``summary_zh``.

    Returns the number of summary **variants** written (each language counts as one).
    """
    init_db()
    langs = agent_summary_languages()
    if summarize_all:
        pending_ids = _select_all_candidate_ids(force=force, langs=langs)
    else:
        pending_ids = _select_candidate_ids(limit=limit, force=force, langs=langs)

    if dry_run:
        label = "all pending" if summarize_all else f"up to {limit}"
        print(f"Would process article(s) ({label}, dry run). Languages: {langs!r}")
        with session_scope() as session:
            for aid in pending_ids:
                a = session.get(Article, aid)
                if not a:
                    continue
                for lang in langs:
                    if not force and _lang_filled(a, lang):
                        continue
                    print(f"  id={a.id} lang={lang} title={a.title[:80]!r}")
        return 0

    client = get_chat_client()
    model_label = chat_model_name()
    if AGENT_LLM_BACKEND == "ollama":
        print(f"LLM: Ollama  model={model_label!r}")
    else:
        print(f"LLM: OpenAI API  model={model_label!r}")
    print(f"Languages: {langs!r}  (en→summary, zh-cn→summary_zh)")
    if summarize_all:
        print("Mode: all pending articles with content.")

    done = 0
    if not pending_ids:
        print("No articles to summarize (need content, and missing target language unless --force).")
        return 0

    for aid in pending_ids:
        with session_scope() as session:
            article = session.get(Article, aid)
            if article is None:
                continue
            if not (article.content and article.content.strip()):
                continue
            user_msg = _build_user_message(article)
            now = datetime.now(timezone.utc)
            for lang in langs:
                if not force and _lang_filled(article, lang):
                    continue
                sp = (
                    system_prompt
                    if system_prompt
                    else get_effective_system_prompt_for_language(lang)
                )
                text = summarize_text(client, system_prompt=sp, user_message=user_msg)
                _apply_summary(article, lang, text, now)
                done += 1
                print(f"Summarized id={article.id} lang={lang!r} ({len(text)} chars)")

    return done


def _base_candidate_query(force: bool, langs: list[str]):
    q = (
        select(Article.id)
        .where(Article.content.isnot(None))
        .where(Article.content != "")
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    )
    if not force:
        q = q.where(_missing_lang_sql_filter(langs))
    return q


def _select_candidate_ids(limit: int, force: bool, langs: list[str]) -> list[int]:
    lim = max(1, min(limit, 500))
    with session_scope() as session:
        q = _base_candidate_query(force, langs).limit(lim)
        return list(session.scalars(q).all())


def _select_all_candidate_ids(force: bool, langs: list[str]) -> list[int]:
    with session_scope() as session:
        q = _base_candidate_query(force, langs)
        return list(session.scalars(q).all())
