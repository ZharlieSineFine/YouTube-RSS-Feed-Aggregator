"""
Run the full daily chain: incremental ingest, then either a minimal "no updates"
email or agent summarization + digest.

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


def main() -> None:
    load_dotenv(_PROJECT_ROOT / ".env", override=True)

    from app.db.session import init_db
    from app.ingest.runner import run_all

    init_db()

    results, _inserted = run_all()
    new_count = sum(len(v) for v in results.values())

    if new_count == 0:
        from app.digest.no_updates import send_no_updates_emails

        send_no_updates_emails()
        print("[daily] No new items from ingest; skipped agent and digest.")
        return

    limit = os.environ.get("AGGREGATOR_AGENT_LIMIT", "50").strip() or "50"
    subprocess.check_call(
        [sys.executable, "-m", "app.agent", "-n", limit],
        cwd=str(_PROJECT_ROOT),
    )
    subprocess.check_call(
        [sys.executable, "-m", "app.digest", "send"],
        cwd=str(_PROJECT_ROOT),
    )
    print("[daily] Done: agent + digest send.")


if __name__ == "__main__":
    main()
