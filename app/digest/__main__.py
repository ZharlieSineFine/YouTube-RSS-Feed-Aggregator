"""CLI: ``python -m app.digest`` — build and optionally send the summary email.

Environment (for ``send``)::

    DIGEST_SMTP_HOST=smtp.example.com
    DIGEST_SMTP_PORT=587
    DIGEST_SMTP_USER=you@example.com
    DIGEST_SMTP_PASSWORD=app-password
    DIGEST_EMAIL_FROM=you@example.com
    DIGEST_EMAIL_TO=reader@example.com,other@example.com

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
from .config import DIGEST_MAX_ARTICLES, DIGEST_SINCE_HOURS, smtp_ready
from .mailer import send_digest_email


def main() -> None:
    init_db()

    p = argparse.ArgumentParser(
        prog="python -m app.digest",
        description="Build HTML digest from Article.summary rows and send via SMTP.",
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

    with session_scope() as session:
        items = load_digest_items(session, limit=limit, since_hours=since)

    subject, plain, html = render_digest_email(items)

    if args.cmd == "preview":
        print(subject)
        print("=" * len(subject))
        print(plain)
        return

    if not args.dry_run and not smtp_ready():
        print(
            "Missing SMTP configuration. Set DIGEST_SMTP_HOST, DIGEST_EMAIL_FROM, "
            "DIGEST_EMAIL_TO (and usually DIGEST_SMTP_USER / DIGEST_SMTP_PASSWORD).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(f"Digest: {len(items)} article(s), subject={subject!r}")
    if args.dry_run:
        print("Dry run: not sending.")
        return

    send_digest_email(subject=subject, text_plain=plain, html_body=html)
    print("Sent.")


if __name__ == "__main__":
    main()
