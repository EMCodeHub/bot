from __future__ import annotations

from datetime import datetime, timezone

from app.db.postgres import get_cursor
from app.models.form_chatbot import FormChatbotPayload
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_form_chatbot_table() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS form_chatbot (
        id SERIAL PRIMARY KEY,
        name TEXT,
        country TEXT,
        email TEXT,
        phone TEXT,
        message TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'medtl_chat_widget',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        notes TEXT DEFAULT '',
        status TEXT DEFAULT 'pending'
    );

    CREATE INDEX IF NOT EXISTS form_chatbot_created_at_idx
        ON form_chatbot (created_at);

    ALTER TABLE form_chatbot ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';
    ALTER TABLE form_chatbot ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
    ALTER TABLE form_chatbot ALTER COLUMN status SET DEFAULT 'pending';
    ALTER TABLE form_chatbot ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'medtl_chat_widget';
    """

    with get_cursor() as (_, cur):
        cur.execute(sql)
        logger.info("form_chatbot table ensured.")


def save_form_submission(payload: FormChatbotPayload) -> int:
    timestamp = payload.created_at or datetime.now(timezone.utc)
    sql = """
        INSERT INTO form_chatbot (
        name, country, email, phone, message, source, created_at, notes, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    with get_cursor() as (_, cur):
        cur.execute(
            sql,
            (
                payload.name,
                payload.country,
                payload.email,
                payload.phone,
                payload.message,
                payload.source,
                timestamp,
                payload.notes or "",
                "pending",
            ),
        )
        row = cur.fetchone()
        submission_id = row["id"]
        logger.info("Stored form_chatbot submission id=%s", submission_id)
        return submission_id
