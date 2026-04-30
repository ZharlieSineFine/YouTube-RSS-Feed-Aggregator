"""Load articles with summaries and render HTML + plain text."""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Source

from .config import (
    DIGEST_SINCE_STRICT_ROLLING,
    DIGEST_SINCE_UTC_CALENDAR_DAYS,
    DIGEST_UI_LANGUAGE,
)


def _digest_published_at_cutoff(since_hours: float) -> datetime:
    """
    Lower bound for ``published_at`` (UTC) when filtering the digest.

    By default uses the **earlier** of:

    - ``now - since_hours`` (rolling window), and
    - midnight UTC at ``DIGEST_SINCE_UTC_CALENDAR_DAYS`` **full days** before today
      (default 2, so the floor is start of the day before *yesterday* UTC, which
      is more inclusive when local "yesterday" is still a prior UTC day).

    Set ``DIGEST_SINCE_STRICT_ROLLING=1`` for a strict rolling window only, or
    ``DIGEST_SINCE_UTC_CALENDAR_DAYS=1`` to match the older "start of yesterday UTC" only.
    """
    now = datetime.now(timezone.utc)
    rolling = now - timedelta(hours=since_hours)
    if DIGEST_SINCE_STRICT_ROLLING:
        return rolling
    days = max(1, int(DIGEST_SINCE_UTC_CALENDAR_DAYS or 1))
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    calendar_floor = today_start - timedelta(days=days)
    return min(rolling, calendar_floor)


def _escape_bold_segments(line: str) -> str:
    """Escape HTML and turn ``**text`` into <strong> (safe, no raw HTML from model)."""
    if not line:
        return ""
    out: List[str] = []
    i = 0
    while i < len(line):
        j = line.find("**", i)
        if j == -1:
            out.append(html.escape(line[i:]))
            break
        out.append(html.escape(line[i:j]))
        k = line.find("**", j + 2)
        if k == -1:
            out.append(html.escape(line[j:]))
            break
        out.append("<strong>" + html.escape(line[j + 2 : k]) + "</strong>")
        i = k + 2
    return "".join(out)


def _summary_to_html(raw: str) -> str:
    """Turn summary text into paragraphs, bullet lists, and bold segments."""
    raw = (raw or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    lines = raw.split("\n")
    chunks: List[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("- "):
            items: List[str] = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                content = lines[i].strip()[2:].strip()
                items.append(f'<li style="margin:0.35em 0;">{_escape_bold_segments(content)}</li>')
                i += 1
            chunks.append(
                '<ul style="margin:0.6em 0 0.75em 0;padding-left:1.25em;color:#334155;line-height:1.5;">'
                + "".join(items)
                + "</ul>"
            )
            continue
        para: List[str] = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("- "):
            para.append(_escape_bold_segments(lines[i].strip()))
            i += 1
        if para:
            body = "<br>\n".join(para)
            chunks.append(
                f'<p style="margin:0.55em 0;line-height:1.6;color:#334155;font-size:15px;">{body}</p>'
            )
    return "\n".join(chunks)


def digest_ui_strings_for(digest_ui_locale: str | None = None) -> dict[str, str]:
    """Localized labels for HTML shell. Pass ``en``, ``zh-cn``, or None (uses ``DIGEST_UI_LANGUAGE``, default English)."""
    if digest_ui_locale is not None and str(digest_ui_locale).strip() != "":
        lang = str(digest_ui_locale).strip().lower()
    else:
        lang = (DIGEST_UI_LANGUAGE or "en").strip().lower()
    zh = lang in ("zh-cn", "zh_cn", "zh-hans", "zh_hans", "zh", "chinese", "cn")
    if zh:
        return {
            "subject_prefix": "AI 资讯摘要",
            "empty_plain": "当前筛选条件下没有可发送的摘要条目。",
            "empty_html": "<p>当前筛选条件下没有可发送的摘要条目。</p>",
            "preheader": "您的 AI 资讯精选摘要 — ",
            "subtitle": "来自您所订阅来源的摘要",
            "footer": "由您的 AI 新闻聚合器发送",
            "html_lang": "zh-Hans",
        }
    return {
        "subject_prefix": "AI news digest",
        "empty_plain": "No summarized articles matched your filters.",
        "empty_html": "<p>No summarized articles matched your filters.</p>",
        "preheader": "Your summarized AI news picks — ",
        "subtitle": "Summaries from your ingested sources",
        "footer": "Sent by your AI news aggregator",
        "html_lang": "en",
    }


def load_digest_items(
    session: Session,
    *,
    limit: int,
    since_hours: float | None,
    summary_locale: str = "en",
) -> List[Dict[str, Any]]:
    """Return plain dicts (safe to use after the session closes).

    ``summary_locale`` ``en`` uses ``Article.summary``; ``zh-cn`` / ``zh`` uses ``Article.summary_zh``.

    When ``since_hours`` is set, ``published_at`` uses :func:`_digest_published_at_cutoff`
    unless ``DIGEST_SINCE_STRICT_ROLLING`` forces a plain rolling window.
    """
    sl = (summary_locale or "en").strip().lower()
    use_zh = sl in ("zh", "zh-cn", "zh_cn", "zh-hans", "zh_hans", "chinese", "cn")
    q = (
        select(Article, Source)
        .join(Source, Article.source_id == Source.id)
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    )
    if use_zh:
        q = q.where(Article.summary_zh.isnot(None)).where(Article.summary_zh != "")
    else:
        q = q.where(Article.summary.isnot(None)).where(Article.summary != "")
    if since_hours is not None:
        cutoff = _digest_published_at_cutoff(since_hours)
        q = q.where(
            (Article.published_at.isnot(None)) & (Article.published_at >= cutoff)
        )
    q = q.limit(max(1, min(limit, 500)))
    rows: List[Dict[str, Any]] = []
    for art, src in session.execute(q).all():
        body = (art.summary_zh or "") if use_zh else (art.summary or "")
        rows.append(
            {
                "title": art.title,
                "title_zh": (art.title_zh or "").strip() or None,
                "url": art.url,
                "summary": body,
                "source_kind": src.kind,
                "published_at": art.published_at,
            }
        )
    return rows


def render_digest_email(
    items: List[Dict[str, Any]],
    *,
    title: str | None = None,
    digest_ui_locale: str | None = None,
    bilingual_titles: bool = False,
) -> tuple[str, str, str]:
    """
    Return ``(subject, text_plain, html)`` for MIME multipart.
    ``digest_ui_locale`` overrides ``DIGEST_UI_LANGUAGE`` for subject/footer strings (e.g. ``en`` vs ``zh-cn``).
    If ``bilingual_titles`` is True and a row has ``title_zh``, show original title plus Chinese translation in the card.
    """
    now = datetime.now(timezone.utc)
    ui = digest_ui_strings_for(digest_ui_locale)
    subject = title or f"{ui['subject_prefix']} - {now.strftime('%Y-%m-%d %H:%M UTC')}"
    if not items:
        plain = ui["empty_plain"]
        h = ui["empty_html"]
        return subject, plain, _wrap_html(h, subject, ui)

    blocks_plain: List[str] = []
    blocks_html: List[str] = []
    for row in items:
        pub = row.get("published_at")
        pub_s = pub.strftime("%Y-%m-%d %H:%M UTC") if pub else "—"
        t_esc = html.escape(row["title"])
        u_esc = html.escape(row["url"])
        url_raw = row["url"]
        k_esc = html.escape(row["source_kind"])
        summary_html = _summary_to_html(row.get("summary") or "")
        title_zh = row.get("title_zh") if bilingual_titles else None
        tzh_esc = html.escape(title_zh.strip()) if title_zh else ""
        zh_title_html = ""
        if title_zh:
            zh_title_html = f"""
      <p style="margin:0 0 10px 0;font-size:16px;line-height:1.45;color:#0f172a;font-weight:600;">
        <span style="color:#64748b;font-size:12px;font-weight:500;margin-right:6px;">译文</span>{tzh_esc}
      </p>"""
        blocks_html.append(
            f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;border-collapse:collapse;">
  <tr>
    <td style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 22px;box-shadow:0 1px 3px rgba(15,23,42,0.06);">
      <p style="margin:0 0 8px 0;font-size:18px;line-height:1.35;font-weight:600;">
        <a href="{html.escape(url_raw, quote=True)}" style="color:#1e3a8a;text-decoration:none;">{t_esc}</a>
        <span style="display:inline-block;margin-left:8px;vertical-align:middle;background:#eef2ff;color:#4338ca;font-size:11px;font-weight:600;letter-spacing:0.02em;padding:3px 10px;border-radius:999px;">{k_esc}</span>
      </p>{zh_title_html}
      <p style="margin:0 0 14px 0;font-size:13px;color:#64748b;">
        <span style="color:#94a3b8;">{pub_s}</span>
      </p>
      <p style="margin:0 0 12px 0;font-size:13px;">
        <a href="{html.escape(url_raw, quote=True)}" style="color:#2563eb;word-break:break-all;">{u_esc}</a>
      </p>
      <div style="border-top:1px solid #f1f5f9;margin:14px 0 0 0;padding-top:14px;">
        {summary_html}
      </div>
    </td>
  </tr>
</table>"""
        )
        zh_plain = f"\n译文：{title_zh.strip()}\n" if (bilingual_titles and title_zh) else "\n"
        blocks_plain.append(
            f"{row['title']}{zh_plain}[{row['source_kind']}]  {pub_s}\n{row['url']}\n\n{row.get('summary', '')}\n\n{'─' * 48}\n"
        )

    plain = "\n".join(blocks_plain)
    body_html = "\n".join(blocks_html)
    return subject, plain, _wrap_html(body_html, subject, ui)


def render_no_updates_email(digest_ui_locale: str | None = None) -> tuple[str, str, str]:
    """
    Minimal digest when incremental ingest found no new items: one line of text, localized subject.
    English: "We have no updates for today." / Chinese: "今日暂无更新。"
    """
    ui = digest_ui_strings_for(digest_ui_locale)
    lang = (str(digest_ui_locale or "en")).strip().lower()
    zh = lang in ("zh", "zh-cn", "zh_cn", "zh-hans", "zh_hans", "chinese", "cn")
    if zh:
        plain_body = "今日暂无更新。"
        subject = f"{ui['subject_prefix']} — 今日暂无更新"
    else:
        plain_body = "We have no updates for today."
        subject = f"{ui['subject_prefix']} — No updates today"
    ui_card = {**ui, "subtitle": ""}
    inner = (
        f'<p style="margin:0;font-size:17px;line-height:1.65;color:#334155;">'
        f"{html.escape(plain_body)}</p>"
    )
    return subject, plain_body, _wrap_html(inner, subject, ui_card)


def _wrap_html(inner: str, heading: str, ui: dict[str, str] | None = None) -> str:
    ui = ui or digest_ui_strings_for(None)
    h = html.escape(heading)
    pre = html.escape(ui["preheader"])
    sub = html.escape(ui["subtitle"])
    foot = html.escape(ui["footer"])
    lang = html.escape(ui["html_lang"])
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:system-ui,-apple-system,'Segoe UI',Roboto,'Noto Sans SC',sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;">{pre}{h}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:640px;border-collapse:collapse;">
          <tr>
            <td style="padding:8px 4px 20px 4px;">
              <h1 style="margin:0;font-size:20px;font-weight:700;color:#0f172a;letter-spacing:-0.02em;">{h}</h1>
              <p style="margin:8px 0 0 0;font-size:13px;color:#64748b;">{sub}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 4px;">
              {inner}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 4px 8px 4px;font-size:12px;color:#94a3b8;text-align:center;">
              {foot}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
