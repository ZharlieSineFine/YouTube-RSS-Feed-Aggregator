"""CLI: ``python -m app.db`` — create schema and show status."""

from __future__ import annotations

import argparse
from urllib.parse import urlparse, urlunparse

from .queries import db_stats, recent_articles
from .session import get_database_url, init_db


def _sanitize_database_url(url: str) -> str:
    """Hide password in database URLs for console output (Postgres, including ``postgresql+psycopg``)."""
    if not url:
        return url
    parsed = urlparse(url)
    if not parsed.password:
        return url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    user = parsed.username or ""
    netloc = f"{user}:***@{host}{port}"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="News aggregator database: create tables and inspect contents.",
        prog="python -m app.db",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="init",
        choices=("init", "stats", "recent"),
        help="init: create tables (default); stats: row counts; recent: list latest articles (add --summaries for full text)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=15,
        help="With 'recent', max rows to print (default 15, max 500)",
    )
    parser.add_argument(
        "--summaries",
        action="store_true",
        help="With 'recent', print full stored summary text when present",
    )
    args = parser.parse_args()

    url = get_database_url()
    print(f"Database URL: {_sanitize_database_url(url)}")

    if args.command == "init":
        init_db()
        stats = db_stats()
        print("Schema ready (create_all).")
        print(f"  sources:  {stats['sources']}")
        print(f"  articles: {stats['articles']}")
        return

    if args.command == "stats":
        init_db()
        stats = db_stats()
        print(f"sources:  {stats['sources']}")
        print(f"articles: {stats['articles']}")
        return

    # recent
    init_db()
    rows = recent_articles(limit=args.limit)
    if not rows:
        print("No articles yet.")
        return
    for r in rows:
        ts = r["published_at"].isoformat() if r["published_at"] else "—"
        print(f"[{r['source_kind']}] {ts}")
        print(f"  {r['title'][:120]}{'…' if len(r['title']) > 120 else ''}")
        if r.get("title_zh"):
            print(f"  title_zh: {r['title_zh'][:120]}{'…' if len(r['title_zh']) > 120 else ''}")
        print(f"  {r['url']}")
        print(f"  content: {r['content_chars']} chars")
        if args.summaries:
            if r.get("summary"):
                sat = r["summarized_at"]
                sat_s = sat.isoformat() if sat else "—"
                print(f"  summarized_at (en): {sat_s}")
                print("  summary (en):")
                for line in (r["summary"] or "").splitlines():
                    print(f"    {line}")
            else:
                print("  summary (en): (none yet)")
            if r.get("summary_zh"):
                satz = r["summarized_at_zh"]
                satz_s = satz.isoformat() if satz else "—"
                print(f"  summarized_at (zh): {satz_s}")
                print("  summary (zh):")
                for line in (r["summary_zh"] or "").splitlines():
                    print(f"    {line}")
            else:
                print("  summary (zh): (none yet)")
        print()


if __name__ == "__main__":
    main()
