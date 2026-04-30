"""SMTP and digest settings (environment variables)."""

from __future__ import annotations

import os
from typing import List


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _float_opt(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "")


# --- SMTP (required to send; preview works without) ---
DIGEST_SMTP_HOST = os.environ.get("DIGEST_SMTP_HOST", "").strip()
DIGEST_SMTP_PORT = _int("DIGEST_SMTP_PORT", 587)
# Set to 1/true for implicit TLS on port 465; otherwise STARTTLS on 587/25.
DIGEST_SMTP_USE_SSL = os.environ.get("DIGEST_SMTP_USE_SSL", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
DIGEST_SMTP_USER = os.environ.get("DIGEST_SMTP_USER", "").strip()
DIGEST_SMTP_PASSWORD = os.environ.get("DIGEST_SMTP_PASSWORD", "")

# From / To
DIGEST_EMAIL_FROM = os.environ.get("DIGEST_EMAIL_FROM", "").strip()
# Comma-separated list of recipients (legacy single digest — English ``summary`` + ``DIGEST_UI_LANGUAGE`` chrome)
DIGEST_EMAIL_TO = os.environ.get("DIGEST_EMAIL_TO", "").strip()
# Split digests: English body from ``Article.summary`` / Chinese from ``Article.summary_zh``
DIGEST_EMAIL_TO_EN = os.environ.get("DIGEST_EMAIL_TO_EN", "").strip()
DIGEST_EMAIL_TO_ZH = os.environ.get("DIGEST_EMAIL_TO_ZH", "").strip()

# Max articles in one email (newest with a summary first).
DIGEST_MAX_ARTICLES = _int("DIGEST_MAX_ARTICLES", 50)
# If set, only include rows with published_at within the last N hours (UTC),
# optionally floored to a UTC midnight (see DIGEST_SINCE_UTC_CALENDAR_DAYS, DIGEST_SINCE_STRICT_ROLLING).
DIGEST_SINCE_HOURS = _float_opt("DIGEST_SINCE_HOURS")
# If false (default): effective cutoff is min(now - N hours, UTC midnight *calendar_floor*) so
# date-only midnight timestamps and "yesterday" across time zones are not dropped. If true: strict
# rolling window only.
DIGEST_SINCE_STRICT_ROLLING = _env_bool("DIGEST_SINCE_STRICT_ROLLING", False)
# How many full UTC days back the non-strict floor can reach (1 = from start of *yesterday* UTC; 2 = from
# start of *two* UTC days ago). Default 2 reduces misses when the digest run is a calendar "day" off
# from `published_at` in UTC.
DIGEST_SINCE_UTC_CALENDAR_DAYS = max(1, _int("DIGEST_SINCE_UTC_CALENDAR_DAYS", 2))

# Email chrome (subject prefix, footer): "en" default, or "zh-cn" / "zh-hans" / "chinese" for Simplified Chinese strings.
DIGEST_UI_LANGUAGE = os.environ.get("DIGEST_UI_LANGUAGE", "").strip().lower()


def parse_recipients(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def digest_use_split_recipients() -> bool:
    """True if at least one of ``DIGEST_EMAIL_TO_EN`` / ``DIGEST_EMAIL_TO_ZH`` is non-empty."""
    return bool(parse_recipients(DIGEST_EMAIL_TO_EN) or parse_recipients(DIGEST_EMAIL_TO_ZH))


def smtp_ready() -> bool:
    if not (DIGEST_SMTP_HOST and DIGEST_EMAIL_FROM):
        return False
    if digest_use_split_recipients():
        return bool(
            parse_recipients(DIGEST_EMAIL_TO_EN) or parse_recipients(DIGEST_EMAIL_TO_ZH)
        )
    return bool(DIGEST_EMAIL_TO and parse_recipients(DIGEST_EMAIL_TO))
