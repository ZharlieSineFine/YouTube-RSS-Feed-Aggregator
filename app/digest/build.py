"""Load articles with summaries and render HTML + plain text."""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Article, Source


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


def load_digest_items(
    session: Session,
    *,
    limit: int,
    since_hours: float | None,
) -> List[Dict[str, Any]]:
    """Return plain dicts (safe to use after the session closes)."""
    q = (
        select(Article, Source)
        .join(Source, Article.source_id == Source.id)
        .where(Article.summary.isnot(None))
        .where(Article.summary != "")
        .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
    )
    if since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        q = q.where(
            (Article.published_at.isnot(None)) & (Article.published_at >= cutoff)
        )
    q = q.limit(max(1, min(limit, 500)))
    rows: List[Dict[str, Any]] = []
    for art, src in session.execute(q).all():
        rows.append(
            {
                "title": art.title,
                "url": art.url,
                "summary": art.summary or "",
                "source_kind": src.kind,
                "published_at": art.published_at,
            }
        )
    return rows


def render_digest_email(
    items: List[Dict[str, Any]],
    *,
    title: str | None = None,
) -> tuple[str, str, str]:
    """
    Return ``(subject, text_plain, html)`` for MIME multipart.
    """
    now = datetime.now(timezone.utc)
    subject = title or f"AI news digest - {now.strftime('%Y-%m-%d %H:%M UTC')}"
    if not items:
        plain = "No summarized articles matched your filters."
        h = "<p>No summarized articles matched your filters.</p>"
        return subject, plain, _wrap_html(h, subject)

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
        blocks_html.append(
            f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;border-collapse:collapse;">
  <tr>
    <td style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 22px;box-shadow:0 1px 3px rgba(15,23,42,0.06);">
      <p style="margin:0 0 8px 0;font-size:18px;line-height:1.35;font-weight:600;">
        <a href="{html.escape(url_raw, quote=True)}" style="color:#1e3a8a;text-decoration:none;">{t_esc}</a>
        <span style="display:inline-block;margin-left:8px;vertical-align:middle;background:#eef2ff;color:#4338ca;font-size:11px;font-weight:600;letter-spacing:0.02em;padding:3px 10px;border-radius:999px;">{k_esc}</span>
      </p>
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
        blocks_plain.append(
            f"{row['title']}\n[{row['source_kind']}]  {pub_s}\n{row['url']}\n\n{row.get('summary', '')}\n\n{'─' * 48}\n"
        )

    plain = "\n".join(blocks_plain)
    body_html = "\n".join(blocks_html)
    return subject, plain, _wrap_html(body_html, subject)


def _wrap_html(inner: str, heading: str) -> str:
    h = html.escape(heading)
    pre = html.escape("Your summarized AI news picks — ")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{h}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;">{pre}{h}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:640px;border-collapse:collapse;">
          <tr>
            <td style="padding:8px 4px 20px 4px;">
              <h1 style="margin:0;font-size:20px;font-weight:700;color:#0f172a;letter-spacing:-0.02em;">{h}</h1>
              <p style="margin:8px 0 0 0;font-size:13px;color:#64748b;">Summaries from your ingested sources</p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 4px;">
              {inner}
            </td>
          </tr>
          <tr>
            <td style="padding:20px 4px 8px 4px;font-size:12px;color:#94a3b8;text-align:center;">
              Sent by your AI news aggregator
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
