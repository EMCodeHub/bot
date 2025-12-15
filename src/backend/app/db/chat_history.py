from typing import List, Dict, Optional

from app.db.postgres import get_cursor
from app.db.chatbot_leads_conversation import (
    extract_phone_and_email,
    save_lead,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_chat_history_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ip TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT DEFAULT ''
    );

    CREATE INDEX IF NOT EXISTS chat_messages_conv_idx
        ON chat_messages (conversation_id, created_at);

    ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS ip TEXT;
    ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
    ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';
    ALTER TABLE chat_messages ALTER COLUMN status SET DEFAULT 'pending';
    """

    with get_cursor() as (_, cur):
        cur.execute(sql)
        logger.info("chat_messages table ensured.")


def save_message(
    conversation_id: str, role: str, content: str, ip: str | None = None
) -> None:
    """
    Insert a single message into chat_messages.
    role should be 'user' or 'assistant'.
    """
    if role == "user":
        try:
            _maybe_record_conversation_lead(conversation_id, content, ip)
        except Exception:
            logger.exception(
                f"Failed to record lead info for conv={conversation_id}"
            )

    sql = """
        INSERT INTO chat_messages (conversation_id, role, content, ip, status)
        VALUES (%s, %s, %s, %s, %s);
    """

    with get_cursor() as (_, cur):
        cur.execute(
            sql,
            (conversation_id, role, content, ip, "pending"),
        )
        logger.debug(
            f"Saved message conv={conversation_id}, role={role}, len={len(content)}"
        )


def get_recent_messages(conversation_id: str, limit: int = 6) -> List[Dict]:
    """
    Return the most recent messages for a conversation, ordered oldest→newest.

    Each row is a dict with: id, conversation_id, created_at, role, content.
    """
    sql = """
        SELECT id, conversation_id, created_at, role, content, ip, status, notes
        FROM chat_messages
        WHERE conversation_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
    """

    try:
        with get_cursor() as (_, cur):
            cur.execute(sql, (conversation_id, limit))
            rows = cur.fetchall()
        rows.reverse()
        return rows
    except Exception as exc:
        logger.exception(
            f"Failed to fetch history for conv={conversation_id}: {exc}"
        )
        return []


def _maybe_record_conversation_lead(
    conversation_id: str, message: str, ip: str | None
) -> None:
    """Detect phone/email in user text and persist to the leads table."""
    payload = extract_phone_and_email(message)
    phone = payload["phone"]
    email = payload["email"]
    if not phone and not email:
        return
    save_lead(conversation_id or "", phone, email, ip=ip)


def init_chatbot_conversations_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS chatbot_conversations (
        conversation_id TEXT PRIMARY KEY,
        status TEXT DEFAULT 'pending',
        notes TEXT DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    ALTER TABLE chatbot_conversations ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
    ALTER TABLE chatbot_conversations ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';
    ALTER TABLE chatbot_conversations ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    ALTER TABLE chatbot_conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    ALTER TABLE chatbot_conversations ALTER COLUMN status SET DEFAULT 'pending';
    """

    with get_cursor() as (_, cur):
        cur.execute(sql)
        logger.info("chatbot_conversations table ensured.")


def ensure_conversation_metadata(conversation_id: str) -> None:
    if not conversation_id:
        return

    sql = """
        INSERT INTO chatbot_conversations (conversation_id, status)
        VALUES (%s, 'pending')
        ON CONFLICT (conversation_id) DO NOTHING;
    """

    with get_cursor() as (_, cur):
        cur.execute(sql, (conversation_id,))


def get_chat_message(message_id: int) -> Optional[Dict]:
    """Retrieve a single chat message row by its primary key."""
    sql = """
        SELECT id, conversation_id, created_at, role, content, ip, status, notes
        FROM chat_messages
        WHERE id = %s;
    """
    with get_cursor() as (_, cur):
        cur.execute(sql, (message_id,))
        return cur.fetchone()


def update_chat_message_metadata(
    message_id: int, *, status: Optional[str] = None, notes: Optional[str] = None
) -> Optional[Dict]:
    """Update the status and/or notes columns for an existing message."""
    updates: List[str] = []
    values: List[Optional[str]] = []
    if status is not None:
        updates.append("status = %s")
        values.append(status)
    if notes is not None:
        updates.append("notes = %s")
        values.append(notes)
    if not updates:
        return get_chat_message(message_id)

    values.append(message_id)
    sql = f"""
        UPDATE chat_messages
        SET {', '.join(updates)}
        WHERE id = %s
        RETURNING id, conversation_id, created_at, role, content, ip, status, notes;
    """

    with get_cursor() as (_, cur):
        cur.execute(sql, tuple(values))
        return cur.fetchone()


def list_conversation_messages(conversation_id: str) -> List[Dict]:
    """Return every message for the supplied conversation."""
    sql = """
        SELECT id, conversation_id, created_at, role, content, ip, status, notes
        FROM chat_messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC
        ;
    """

    try:
        with get_cursor() as (_, cur):
            cur.execute(sql, (conversation_id,))
            return cur.fetchall()
    except Exception as exc:
        logger.exception(
            f"Failed to list messages for conv={conversation_id}: {exc}"
        )
        return []
