"""Outbound email delivery for notifications.

Configured entirely through environment variables; when SMTP_HOST is not
set, delivery is skipped and notifications exist only in the database log
(which is always written regardless).

  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
  SMTP_FROM (default no-reply@corrective-actions.local),
  SMTP_STARTTLS (default "1")
"""
import os
import smtplib
import sqlite3
from email.message import EmailMessage
from typing import Optional


def _resolve_email(conn: sqlite3.Connection, recipient: str) -> Optional[str]:
    """Recipient strings are emails, user names, or team labels."""
    if "@" in recipient:
        return recipient
    row = conn.execute(
        "SELECT email FROM users WHERE name = ? AND active = 1", (recipient,)).fetchone()
    return row["email"] if row else None


def send_email(conn: sqlite3.Connection, recipient: str, subject: str, body: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    if not host:
        return False
    to_addr = _resolve_email(conn, recipient)
    if not to_addr:
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "no-reply@corrective-actions.local")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as smtp:
            if os.environ.get("SMTP_STARTTLS", "1") == "1":
                smtp.starttls()
            user = os.environ.get("SMTP_USER")
            if user:
                smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        print(f"[notify] email to {to_addr} failed: {exc}")
        return False
