"""HTML digest generation and SMTP delivery."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# python -m app.digest loads this package before __main__.py; load .env before any
# submodule imports config (otherwise empty env wins over the file).
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from .build import load_digest_items, render_digest_email
from .config import smtp_ready
from .mailer import send_digest_email

__all__ = [
    "load_digest_items",
    "render_digest_email",
    "send_digest_email",
    "smtp_ready",
]
