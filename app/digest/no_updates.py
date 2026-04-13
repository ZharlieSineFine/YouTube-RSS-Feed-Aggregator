"""Send a minimal email when incremental ingest found no new items (daily run)."""

from __future__ import annotations

from .build import render_no_updates_email
from .config import (
    DIGEST_EMAIL_TO,
    DIGEST_EMAIL_TO_EN,
    DIGEST_EMAIL_TO_ZH,
    DIGEST_UI_LANGUAGE,
    digest_use_split_recipients,
    parse_recipients,
    smtp_ready,
)
from .mailer import send_digest_email


def _legacy_digest_locale() -> str:
    """Match legacy single-list digest chrome (DIGEST_UI_LANGUAGE)."""
    l = (DIGEST_UI_LANGUAGE or "en").strip().lower()
    if l in ("zh", "zh-cn", "zh_cn", "zh-hans", "zh_hans", "chinese", "cn"):
        return "zh"
    return "en"


def send_no_updates_emails() -> None:
    """Send localized one-line emails to EN and/or ZH lists (or legacy single list)."""
    if not smtp_ready():
        print("[digest] SMTP not configured; skip no-updates email.")
        return
    if digest_use_split_recipients():
        en_to = parse_recipients(DIGEST_EMAIL_TO_EN)
        zh_to = parse_recipients(DIGEST_EMAIL_TO_ZH)
        if en_to:
            subj, plain, html_body = render_no_updates_email("en")
            send_digest_email(
                subject=subj, text_plain=plain, html_body=html_body, to_addresses=en_to
            )
            print(f"[digest] No-updates email sent to EN ({len(en_to)} recipient(s)).")
        if zh_to:
            subj, plain, html_body = render_no_updates_email("zh")
            send_digest_email(
                subject=subj, text_plain=plain, html_body=html_body, to_addresses=zh_to
            )
            print(f"[digest] No-updates email sent to ZH ({len(zh_to)} recipient(s)).")
        if not en_to and not zh_to:
            print("[digest] No DIGEST_EMAIL_TO_EN / DIGEST_EMAIL_TO_ZH; skip no-updates email.")
        return
    to_addrs = parse_recipients(DIGEST_EMAIL_TO)
    if not to_addrs:
        print("[digest] No DIGEST_EMAIL_TO; skip no-updates email.")
        return
    subj, plain, html_body = render_no_updates_email(_legacy_digest_locale())
    send_digest_email(
        subject=subj, text_plain=plain, html_body=html_body, to_addresses=to_addrs
    )
    print(f"[digest] No-updates email sent ({len(to_addrs)} recipient(s)).")
