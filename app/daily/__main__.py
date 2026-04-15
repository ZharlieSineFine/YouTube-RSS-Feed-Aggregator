"""
Run the full daily chain: incremental ingest, then agent (if new items), then digest.

If there are summarized articles in the digest window, send the full digest.
If no summarized articles match, send the "no updates" email.

Intended for Task Scheduler every 24h. Set DIGEST_SINCE_HOURS=24 (or similar)
so the digest window matches your schedule.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _has_digest_items() -> bool:
    """Return True if at least one summarized article exists in the digest window."""
    from app.db.session import session_scope
    from app.digest.build import load_digest_items
    from app.digest.config import DIGEST_MAX_ARTICLES, DIGEST_SINCE_HOURS

    with session_scope() as session:
        items = load_digest_items(
            session,
            limit=DIGEST_MAX_ARTICLES,
            since_hours=DIGEST_SINCE_HOURS,
            summary_locale="en",
        )
    return len(items) > 0


def main() -> None:
    load_dotenv(_PROJECT_ROOT / ".env", override=True)

    from app.db.session import init_db
    from app.ingest.runner import run_all

    init_db()

    results, _inserted = run_all()
    new_count = sum(len(v) for v in results.values())

    if new_count > 0:
        limit = os.environ.get("AGGREGATOR_AGENT_LIMIT", "50").strip() or "50"
        subprocess.check_call(
            [sys.executable, "-m", "app.agent", "-n", limit],
            cwd=str(_PROJECT_ROOT),
        )
        print(f"[daily] Agent processed up to {limit} new articles.")

    if _has_digest_items():
        subprocess.check_call(
            [sys.executable, "-m", "app.digest", "send"],
            cwd=str(_PROJECT_ROOT),
        )
        print("[daily] Digest sent.")
    else:
        from app.digest.no_updates import send_no_updates_emails

        send_no_updates_emails()
        print("[daily] No summarized articles in digest window; sent no-updates email.")


if __name__ == "__main__":
    main()
