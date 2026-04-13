"""CLI: ``python -m app.agent`` — summarize articles in the database.

**OpenAI (default):** set ``OPENAI_API_KEY`` (e.g. in ``.env``).

**Ollama (local):** ``ollama pull qwen3:14b``, then ``AGENT_LLM_BACKEND=ollama``
(optional: ``OLLAMA_MODEL=...`` if the tag differs).

Examples::

    uv run python -m app.agent --dry-run
    uv run python -m app.agent --limit 5
    uv run python -m app.agent --all
    set AGENT_LLM_BACKEND=ollama && uv run python -m app.agent -n 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from .summarize import summarize_pending


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python -m app.agent",
        description="Summarize ingested articles and store summaries in the database.",
    )
    p.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="Max articles to process (default 10; ignored with --all)",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Summarize every ingested article that has content and no summary yet",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidate articles without calling the API",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-summarize even if summary already exists",
    )
    args = p.parse_args()
    if not args.all and args.limit < 1:
        print("--limit must be >= 1 (or use --all)", file=sys.stderr)
        raise SystemExit(2)
    n = summarize_pending(
        limit=args.limit,
        summarize_all=args.all,
        force=args.force,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        print(f"Done. Updated {n} article(s).")


if __name__ == "__main__":
    main()
