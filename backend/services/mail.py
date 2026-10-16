"""Outbound email via SMTP. Returns False (never raises) when SMTP is not configured or fails."""
import smtplib
from email.message import EmailMessage

from .. import config


def mail_enabled() -> bool:
    return bool(config.SMTP_HOST)


def send_mail(to: str, subject: str, body: str) -> bool:
    if not mail_enabled() or not to:
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, config.SMTP_FROM, to
    msg.set_content(body)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        return False
