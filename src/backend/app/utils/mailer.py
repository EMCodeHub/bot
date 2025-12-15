import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _build_lead_body(lead_data: Dict[str, Any]) -> str:
    lines = ["A client give this information during the chatbot conversation:"]
    for label, key in [
        ("Conversation ID", "conversation_id"),
        ("Phone", "phone"),
        ("Email", "email"),
        ("Status", "status"),
        ("IP", "ip"),
        ("Timestamp", "timestamp"),
        ("Notes", "notes"),
    ]:
        lines.append(f"+ {label}: {_format_value(lead_data.get(key))}")
    return "\n".join(lines)


def send_lead_notification(lead_data: Dict[str, Any]) -> None:
    if not settings.lead_notification_enabled:
        logger.debug("Lead notification is disabled in settings.")
        return

    recipients = [
        recipient.strip()
        for recipient in settings.lead_notification_recipients
        if recipient and recipient.strip()
    ]
    if not recipients:
        logger.warning("Lead notification recipients list is empty; skipping email.")
        return

    if not settings.smtp_host:
        logger.warning("SMTP host is not configured; skipping lead notification.")
        return

    message = EmailMessage()
    message["Subject"] = settings.lead_notification_subject
    message["From"] = settings.lead_notification_from
    message["To"] = ", ".join(recipients)
    message.set_content(_build_lead_body(lead_data))

    server_cls = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    try:
        with server_cls(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout
        ) as smtp:
            if not settings.smtp_use_ssl and settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        logger.info("Lead notification email sent to %s", ", ".join(recipients))
    except Exception as exc:
        logger.exception("Failed to send lead notification email: %s", exc)
