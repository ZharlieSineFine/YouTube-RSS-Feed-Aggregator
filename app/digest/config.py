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
# Comma-separated list of recipients
DIGEST_EMAIL_TO = os.environ.get("DIGEST_EMAIL_TO", "").strip()

# Max articles in one email (newest with a summary first).
DIGEST_MAX_ARTICLES = _int("DIGEST_MAX_ARTICLES", 50)
# If set, only include rows with published_at within the last N hours (UTC).
DIGEST_SINCE_HOURS = _float_opt("DIGEST_SINCE_HOURS")


def parse_recipients(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def smtp_ready() -> bool:
    return bool(
        DIGEST_SMTP_HOST
        and DIGEST_EMAIL_FROM
        and DIGEST_EMAIL_TO
        and parse_recipients(DIGEST_EMAIL_TO)
    )
