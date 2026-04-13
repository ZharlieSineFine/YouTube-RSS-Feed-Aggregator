"""Send digest via SMTP (STARTTLS or SSL)."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from .config import (
    DIGEST_EMAIL_FROM,
    DIGEST_EMAIL_TO,
    DIGEST_SMTP_HOST,
    DIGEST_SMTP_PASSWORD,
    DIGEST_SMTP_PORT,
    DIGEST_SMTP_USE_SSL,
    DIGEST_SMTP_USER,
    parse_recipients,
)


def send_digest_email(
    *,
    subject: str,
    text_plain: str,
    html_body: str,
    to_addresses: List[str] | None = None,
) -> None:
    """Send multipart/alternative email. ``to_addresses`` defaults to ``DIGEST_EMAIL_TO``."""
    from_addr = DIGEST_EMAIL_FROM
    recipients = (
        to_addresses
        if to_addresses is not None
        else parse_recipients(DIGEST_EMAIL_TO)
    )
    if not from_addr or not recipients:
        raise ValueError("DIGEST_EMAIL_FROM and DIGEST_EMAIL_TO must be set.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    host = DIGEST_SMTP_HOST
    port = DIGEST_SMTP_PORT
    user = DIGEST_SMTP_USER
    password = DIGEST_SMTP_PASSWORD

    if DIGEST_SMTP_USE_SSL:
        with smtplib.SMTP_SSL(host, port, timeout=60) as smtp:
            if user:
                smtp.login(user, password)
            smtp.sendmail(from_addr, recipients, msg.as_string())
        return

    with smtplib.SMTP(host, port, timeout=60) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.sendmail(from_addr, recipients, msg.as_string())
