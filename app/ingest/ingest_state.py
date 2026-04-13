"""Persistent watermarks for incremental ingestion (only new items since last run)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar

try:
    from .scrapers.cache import get_cache_dir
except ImportError:
    try:
        from scrapers.cache import get_cache_dir
    except ImportError:
        from app.ingest.scrapers.cache import get_cache_dir

STATE_FILENAME = "ingest_state.json"
STATE_VERSION = 1

T = TypeVar("T")


def state_path() -> Path:
    return get_cache_dir() / STATE_FILENAME


def load_state() -> Dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {"version": STATE_VERSION, "youtube": {}, "anthropic": None, "openai": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": STATE_VERSION, "youtube": {}, "anthropic": None, "openai": None}
        data.setdefault("version", STATE_VERSION)
        data.setdefault("youtube", {})
        data.setdefault("anthropic", None)
        data.setdefault("openai", None)
        return data
    except (json.JSONDecodeError, OSError):
        return {"version": STATE_VERSION, "youtube": {}, "anthropic": None, "openai": None}


def save_state(state: Dict[str, Any]) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {**state, "version": STATE_VERSION}
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def filter_incremental_published(
    items: List[T],
    published_at_fn,
    watermark: Optional[datetime],
    now: datetime,
    first_run_lookback_hours: int,
) -> List[T]:
    """
    Keep items strictly after watermark, or if no watermark yet, only within first_run window.
    """
    if not items:
        return []

    if watermark is None:
        cutoff = now - timedelta(hours=first_run_lookback_hours)
        return [x for x in items if published_at_fn(x) is not None and published_at_fn(x) >= cutoff]

    return [x for x in items if published_at_fn(x) is not None and published_at_fn(x) > watermark]


def merge_youtube_watermarks(
    state: Dict[str, Any],
    channel_ids: List[str],
    new_by_channel: Dict[str, List[Any]],
) -> Dict[str, Any]:
    youtube = dict(state.get("youtube") or {})
    for ch in channel_ids:
        new_items = new_by_channel.get(ch) or []
        if not new_items:
            continue
        max_dt = max(v.published_at for v in new_items)
        old_s = youtube.get(ch)
        old_dt = parse_iso(old_s) if old_s else None
        if old_dt is None or max_dt > old_dt:
            youtube[ch] = max_dt.isoformat()
    state["youtube"] = youtube
    return state


def merge_scalar_watermark(
    state: Dict[str, Any],
    key: str,
    new_items: List[Any],
    published_at_fn,
) -> Dict[str, Any]:
    dates = [published_at_fn(x) for x in new_items if published_at_fn(x) is not None]
    if not dates:
        return state
    max_dt = max(dates)
    old_s = state.get(key)
    old_dt = parse_iso(old_s) if old_s else None
    if old_dt is None or max_dt > old_dt:
        state[key] = max_dt.isoformat()
    return state
