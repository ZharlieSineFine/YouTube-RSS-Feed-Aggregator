"""
Configuration for content sources.

Cache TTL (not set here): export CACHE_MAX_AGE_HOURS=6 (default) so .cache/ entries
refetch after a few hours. Use CACHE_MAX_AGE_HOURS=0 only if you want no expiry.
Disable caching entirely: USE_CACHE=0

Incremental ingest: watermarks in .cache/ingest_state.json — delete that file to
reset "first run" (bootstrap window only).

Database: set PERSIST_TO_DB=0 to skip writing ingest results to SQLite (see app/db/).
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "")


# After each successful run_all(), upsert into DB (default SQLite under data/).
PERSIST_TO_DB = _env_bool("PERSIST_TO_DB", True)

# --- Incremental mode (default): only return items newer than last successful run ---
# How far back RSS/HTML queries go (must be larger than the longest gap between runs).
FETCH_LOOKBACK_HOURS = 336  # 14 days

# When there is no per-source watermark yet (new channel / first run): only items from the last N hours.
# Should be >= the age spread you expect in ``FETCH_LOOKBACK_HOURS`` feeds, or new channels (e.g. Fireship)
# can yield 0 rows until you backfill. Aligned with feed window by default.
FIRST_RUN_LOOKBACK_HOURS = 336  # 14 days, same order of magnitude as FETCH_LOOKBACK_HOURS

# Set False to use legacy rolling window only (HOURS_BACK_LEGACY below).
INCREMENTAL_INGEST = True

# Legacy: used only when INCREMENTAL_INGEST is False — items published in the last N hours.
HOURS_BACK_LEGACY = 720

# YouTube channel IDs to monitor
YOUTUBE_CHANNELS = [
    "UC11aHtNnc5bEPLI4jf6mnYg",  # Predictive History
    "UCsBjURrPoezykLs9EqgamOA",  # Fireship — https://www.youtube.com/@Fireship
]
