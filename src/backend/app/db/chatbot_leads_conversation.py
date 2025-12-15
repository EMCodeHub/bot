import re
from datetime import datetime, timezone
from typing import Dict, Optional

import phonenumbers
from phonenumbers import PhoneNumberFormat, PhoneNumberMatcher

from app.db.postgres import get_connection, get_cursor
from app.utils.logger import get_logger
from app.utils.mailer import send_lead_notification

logger = get_logger(__name__)


def get_conn():
    return get_connection()

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
)
PHONE_FALLBACK_REGEX = re.compile(r"\b\+?[\d\-\s\(\)]{7,}\d\b")


def init_chatbot_leads_conversation_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS chatbot_leads_conversation (
        id SERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT DEFAULT '',
        ip TEXT,
        "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS chatbot_leads_conv_idx
        ON chatbot_leads_conversation (conversation_id, "timestamp");

    ALTER TABLE chatbot_leads_conversation ADD COLUMN IF NOT EXISTS ip TEXT;
    ALTER TABLE chatbot_leads_conversation ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
    ALTER TABLE chatbot_leads_conversation ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';
    ALTER TABLE chatbot_leads_conversation ALTER COLUMN status SET DEFAULT 'pending';
    """

    with get_cursor() as (_, cur):
        cur.execute(sql)
        logger.info("chatbot_leads_conversation table ensured.")


def _extract_email(message: str) -> Optional[str]:
    match = EMAIL_REGEX.search(message)
    if match:
        return match.group(0).lower()
    return None


def _extract_phone(message: str) -> Optional[str]:
    try:
        matcher = PhoneNumberMatcher(message, "ZZ")
    except Exception as exc:
        logger.debug(f"PhoneNumberMatcher init failed: {exc}")
        return None

    for match in matcher:
        number = match.number
        if phonenumbers.is_valid_number(number):
            formatted = phonenumbers.format_number(number, PhoneNumberFormat.E164)
            return formatted
    fallback = PHONE_FALLBACK_REGEX.search(message)
    if fallback:
        digits_only = re.sub(r"\D", "", fallback.group(0))
        if 7 <= len(digits_only) <= 15:
            logger.debug(f"Fallback phone match: {digits_only}")
            return digits_only
    return None


def extract_phone_and_email(message: str) -> Dict[str, Optional[str]]:
    message = (message or "").strip()
    if not message:
        return {"phone": None, "email": None}

    phone = _extract_phone(message)
    email = _extract_email(message)
    return {"phone": phone, "email": email}


def save_lead(
    conversation_id: str,
    phone: Optional[str],
    email: Optional[str],
    status: str = "pending",
    timestamp: Optional[datetime] = None,
    ip: Optional[str] = None,
) -> None:
    if not phone and not email:
        return

    when = timestamp or datetime.now(timezone.utc)
    sql = """
        INSERT INTO chatbot_leads_conversation (
            conversation_id, phone, email, status, ip, "timestamp"
        )
        VALUES (%s, %s, %s, %s, %s, %s);
    """

    with get_cursor() as (_, cur):
        cur.execute(
            sql, (conversation_id, phone, email, status, ip, when)
        )
        logger.info(
            f"Saved lead conv={conversation_id}, phone={phone}, email={email}, status={status}, ip={ip}"
        )
        lead_record = {
            "conversation_id": conversation_id,
            "phone": phone,
            "email": email,
            "status": status,
            "ip": ip,
            "timestamp": when,
            "notes": "",
        }
        send_lead_notification(lead_record)
