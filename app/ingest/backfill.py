"""One-shot backfill: fetch a rolling time window (non-incremental) and persist to the DB.

Use when:
- You ran ingest before ``PERSIST_TO_DB`` was enabled, or
- Incremental watermarks mean the next run returns no rows, but you still want
  recent items loaded into SQLite/Postgres.

Does **not** reset ``.cache/ingest_state.json``; incremental runs afterward behave
as before. To re-seed incremental "new since last run" only, see config docs on
deleting the state file.

Usage::

    uv run python -m app.ingest.backfill

Override the window (hours)::

    uv run python -m app.ingest.backfill 168
"""

from __future__ import annotations

import sys

from .config import HOURS_BACK_LEGACY
from .runner import run_all


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    hours = HOURS_BACK_LEGACY
    if argv:
        try:
            hours = int(argv[0])
        except ValueError:
            print(f"Usage: python -m app.ingest.backfill [{HOURS_BACK_LEGACY}]", file=sys.stderr)
            raise SystemExit(2) from None
        if hours < 1:
            print("hours must be >= 1", file=sys.stderr)
            raise SystemExit(2)
    print(f"Backfill: rolling window = last {hours} hours (non-incremental), then persist.\n")
    _results, inserted = run_all(hours_back=hours, incremental=False)
    print(f"\nBackfill inserted {inserted} new row(s).")


if __name__ == "__main__":
    main()
