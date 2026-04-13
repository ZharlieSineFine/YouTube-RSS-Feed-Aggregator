"""CLI: ``python -m app.digest`` — build and optionally send the summary email.

Environment (for ``send``)::

    DIGEST_SMTP_HOST=smtp.example.com
    DIGEST_SMTP_PORT=587
    DIGEST_SMTP_USER=you@example.com
    DIGEST_SMTP_PASSWORD=app-password
    DIGEST_EMAIL_FROM=you@example.com

    # Single digest (legacy): ``DIGEST_EMAIL_TO`` + optional ``DIGEST_UI_LANGUAGE``

    # Split: English vs Chinese bodies (``Article.summary`` vs ``Article.summary_zh``)::
    #   DIGEST_EMAIL_TO_EN=a@x.com,b@x.com
    #   DIGEST_EMAIL_TO_ZH=c@x.com,d@x.com

Optional::

    DIGEST_MAX_ARTICLES=50
    DIGEST_SINCE_HOURS=168
    DIGEST_SMTP_USE_SSL=1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Package __init__ also loads .env; keep this so imports below see values if __main__ is run alone.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from app.db.session import init_db, session_scope

from .build import load_digest_items, render_digest_email
from .config import (
    DIGEST_EMAIL_TO_EN,
    DIGEST_EMAIL_TO_ZH,
    DIGEST_MAX_ARTICLES,
    DIGEST_SINCE_HOURS,
    digest_use_split_recipients,
    parse_recipients,
    smtp_ready,
)
from .mailer import send_digest_email


def main() -> None:
    init_db()

    p = argparse.ArgumentParser(
        prog="python -m app.digest",
        description="Build HTML digest from article summaries and send via SMTP.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    preview = sub.add_parser("preview", help="Print plain text to stdout")
    preview.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help=f"Max articles (default: DIGEST_MAX_ARTICLES or {DIGEST_MAX_ARTICLES})",
    )
    preview.add_argument(
        "--since-hours",
        type=float,
        default=None,
        help="Override DIGEST_SINCE_HOURS (only articles published within this many hours)",
    )

    send_p = sub.add_parser("send", help="Send email (requires SMTP env)")
    send_p.add_argument("-n", "--limit", type=int, default=None)
    send_p.add_argument("--since-hours", type=float, default=None)
    send_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Build message and print stats only; do not connect to SMTP",
    )

    args = p.parse_args()
    limit = args.limit if args.limit is not None else DIGEST_MAX_ARTICLES
    since = args.since_hours if args.since_hours is not None else DIGEST_SINCE_HOURS

    if digest_use_split_recipients():
        _run_split(args, limit=limit, since=since)
        return

    with session_scope() as session:
        items = load_digest_items(session, limit=limit, since_hours=since, summary_locale="en")

    subject, plain, html = render_digest_email(items, bilingual_titles=False)

    if args.cmd == "preview":
        print(subject)
        print("=" * len(subject))
        print(plain)
        return

    if not args.dry_run and not smtp_ready():
        print(
            "Missing SMTP configuration. Set DIGEST_SMTP_HOST, DIGEST_EMAIL_FROM, "
            "DIGEST_EMAIL_TO (or DIGEST_EMAIL_TO_EN / DIGEST_EMAIL_TO_ZH), "
            "and usually DIGEST_SMTP_USER / DIGEST_SMTP_PASSWORD.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(f"Digest: {len(items)} article(s), subject={subject!r}")
    if args.dry_run:
        print("Dry run: not sending.")
        return

    send_digest_email(subject=subject, text_plain=plain, html_body=html)
    print("Sent.")


def _run_split(args: argparse.Namespace, *, limit: int, since: float | None) -> None:
    en_to = parse_recipients(DIGEST_EMAIL_TO_EN)
    zh_to = parse_recipients(DIGEST_EMAIL_TO_ZH)

    if not en_to and not zh_to:
        print(
            "Split mode: set DIGEST_EMAIL_TO_EN and/or DIGEST_EMAIL_TO_ZH (comma-separated).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.cmd == "preview":
        if en_to:
            with session_scope() as session:
                items_en = load_digest_items(
                    session, limit=limit, since_hours=since, summary_locale="en"
                )
            subject, plain, html = render_digest_email(
                items_en, digest_ui_locale="en", bilingual_titles=False
            )
            print("--- English digest (Article.summary) ---")
            print(subject)
            print("=" * len(subject))
            print(plain)
            print()
        if zh_to:
            with session_scope() as session:
                items_zh = load_digest_items(
                    session, limit=limit, since_hours=since, summary_locale="zh-cn"
                )
            subject, plain, html = render_digest_email(
                items_zh, digest_ui_locale="zh-cn", bilingual_titles=True
            )
            print("--- Chinese digest (Article.summary_zh) ---")
            print(subject)
            print("=" * len(subject))
            print(plain)
        return

    if not args.dry_run and not smtp_ready():
        print(
            "Missing SMTP configuration. Set DIGEST_SMTP_HOST, DIGEST_EMAIL_FROM, "
            "DIGEST_EMAIL_TO_EN and/or DIGEST_EMAIL_TO_ZH, "
            "and usually DIGEST_SMTP_USER / DIGEST_SMTP_PASSWORD.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if en_to:
        with session_scope() as session:
            items_en = load_digest_items(
                session, limit=limit, since_hours=since, summary_locale="en"
            )
        subject, plain, html = render_digest_email(
            items_en, digest_ui_locale="en", bilingual_titles=False
        )
        print(f"English digest: {len(items_en)} article(s), subject={subject!r}")
        if args.dry_run:
            print("Dry run: not sending English.")
        else:
            send_digest_email(subject=subject, text_plain=plain, html_body=html, to_addresses=en_to)
            print(f"Sent English digest to {len(en_to)} recipient(s).")

    if zh_to:
        with session_scope() as session:
            items_zh = load_digest_items(
                session, limit=limit, since_hours=since, summary_locale="zh-cn"
            )
        subject, plain, html = render_digest_email(
            items_zh, digest_ui_locale="zh-cn", bilingual_titles=True
        )
        print(f"Chinese digest: {len(items_zh)} article(s), subject={subject!r}")
        if args.dry_run:
            print("Dry run: not sending Chinese.")
        else:
            send_digest_email(subject=subject, text_plain=plain, html_body=html, to_addresses=zh_to)
            print(f"Sent Chinese digest to {len(zh_to)} recipient(s).")


if __name__ == "__main__":
    main()
