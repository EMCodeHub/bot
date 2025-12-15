from typing import Any, Dict, List, Optional, Tuple

from app.db.postgres import get_cursor
from app.db.chat_history import list_conversation_messages

FORM_CHATBOT_FIELDS = {
    "name",
    "country",
    "email",
    "phone",
    "message",
    "source",
    "notes",
    "status",
}
LEAD_FIELDS = {
    "conversation_id",
    "phone",
    "email",
    "status",
    "notes",
    "ip",
    "timestamp",
}

CONVERSATION_METADATA_FIELDS = {"status", "notes"}


# --- form_chatbot helpers ----------------------------------------------------------------

def list_form_submissions(limit: int = 100, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    sql = """
    SELECT id, name, country, email, phone, message, source, created_at, notes, status
    FROM form_chatbot
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s;
    """
    with get_cursor() as (_, cur):
        cur.execute(sql, (limit, offset))
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*)::INT AS total FROM form_chatbot")
        total = cur.fetchone()["total"]
    return rows, total


def get_form_submission(submission_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as (_, cur):
        cur.execute(
        """
        SELECT id, name, country, email, phone, message, source, created_at, notes, status
        FROM form_chatbot
        WHERE id = %s
        """,
        (submission_id,),
    )
        return cur.fetchone()


def update_form_submission(submission_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {k: v for k, v in updates.items() if k in FORM_CHATBOT_FIELDS}
    if not allowed:
        return None

    expressions = []
    values: List[Any] = []
    for idx, (field, value) in enumerate(allowed.items(), start=1):
        expressions.append(f"{field} = %s")
        values.append(value)
    values.append(submission_id)

    with get_cursor() as (_, cur):
        cur.execute(
            f"UPDATE form_chatbot SET {', '.join(expressions)} WHERE id = %s RETURNING *",
            tuple(values),
        )
        return cur.fetchone()


def delete_form_submission(submission_id: int) -> bool:
    with get_cursor() as (_, cur):
        cur.execute("DELETE FROM form_chatbot WHERE id = %s", (submission_id,))
        deleted = cur.rowcount > 0
        return deleted


# --- chatbot_leads_conversation helpers ----------------------------------------------------

def list_chatbot_leads(limit: int = 100, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    sql = """
    SELECT id, conversation_id, phone, email, status, notes, ip, "timestamp"
    FROM chatbot_leads_conversation
    ORDER BY "timestamp" DESC
    LIMIT %s OFFSET %s;
    """
    with get_cursor() as (_, cur):
        cur.execute(sql, (limit, offset))
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*)::INT AS total FROM chatbot_leads_conversation")
        total = cur.fetchone()["total"]
    return rows, total


def get_chatbot_lead(lead_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as (_, cur):
        cur.execute(
        """
        SELECT id, conversation_id, phone, email, status, notes, ip, "timestamp"
        FROM chatbot_leads_conversation
        WHERE id = %s
        """,
        (lead_id,),
    )
        return cur.fetchone()


def update_chatbot_lead(lead_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    allowed = {k: v for k, v in updates.items() if k in LEAD_FIELDS}
    if not allowed:
        return None

    expressions: List[str] = []
    values: List[Any] = []
    for field, value in allowed.items():
        expressions.append(f"{field} = %s")
        values.append(value)
    values.append(lead_id)

    with get_cursor() as (_, cur):
        cur.execute(
            f"UPDATE chatbot_leads_conversation SET {', '.join(expressions)} WHERE id = %s RETURNING *",
            tuple(values),
        )
        return cur.fetchone()


def delete_chatbot_lead(lead_id: int) -> bool:
    with get_cursor() as (_, cur):
        cur.execute("DELETE FROM chatbot_leads_conversation WHERE id = %s", (lead_id,))
        return cur.rowcount > 0


# --- chatbot_conversations helpers --------------------------------------------------------

def list_conversations(limit: int = 100, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
    sql = """
    SELECT
        s.conversation_id,
        s.started_at,
        s.updated_at,
        s.message_count,
        m.role AS last_role,
        m.content AS last_message,
        m.ip AS last_ip,
        c.status,
        c.notes
    FROM (
        SELECT
            conversation_id,
            MIN(created_at) AS started_at,
            MAX(created_at) AS updated_at,
            COUNT(*) AS message_count,
            MAX(id) AS last_message_id
        FROM chat_messages
        GROUP BY conversation_id
    ) s
    LEFT JOIN chat_messages m ON m.id = s.last_message_id
    LEFT JOIN chatbot_conversations c ON c.conversation_id = s.conversation_id
    ORDER BY s.updated_at DESC
    LIMIT %s OFFSET %s;
    """
    with get_cursor() as (_, cur):
        cur.execute(sql, (limit, offset))
        rows = cur.fetchall()
        cur.execute(
            """
            SELECT COUNT(*)::INT AS total
            FROM (
                SELECT conversation_id
                FROM chat_messages
                GROUP BY conversation_id
            ) summary;
            """
        )
        total = cur.fetchone()["total"]
    return rows, total


def get_conversation_summary(conversation_id: str) -> Optional[Dict[str, Any]]:
    sql = """
    SELECT
        s.conversation_id,
        s.started_at,
        s.updated_at,
        s.message_count,
        m.role AS last_role,
        m.content AS last_message,
        m.ip AS last_ip,
        c.status,
        c.notes
    FROM (
        SELECT
            conversation_id,
            MIN(created_at) AS started_at,
            MAX(created_at) AS updated_at,
            COUNT(*) AS message_count,
            MAX(id) AS last_message_id
        FROM chat_messages
        WHERE conversation_id = %s
        GROUP BY conversation_id
    ) s
    LEFT JOIN chat_messages m ON m.id = s.last_message_id
    LEFT JOIN chatbot_conversations c ON c.conversation_id = s.conversation_id;
    """
    with get_cursor() as (_, cur):
        cur.execute(sql, (conversation_id,))
        return cur.fetchone()


def update_conversation_metadata(conversation_id: str, updates: Dict[str, Any]) -> bool:
    allowed = {k: v for k, v in updates.items() if k in CONVERSATION_METADATA_FIELDS}
    if not allowed:
        return False

    with get_cursor() as (_, cur):
        cur.execute(
            """
            INSERT INTO chatbot_conversations (conversation_id, status)
            VALUES (%s, 'pending')
            ON CONFLICT (conversation_id) DO NOTHING
            """,
            (conversation_id,),
        )
        expressions: List[str] = []
        values: List[Any] = []
        for field, value in allowed.items():
            expressions.append(f"{field} = %s")
            values.append(value)
        values.append(conversation_id)
        cur.execute(
            f"UPDATE chatbot_conversations SET {', '.join(expressions)}, updated_at = NOW() WHERE conversation_id = %s",
            tuple(values),
        )
    return True


def rename_conversation(old_id: str, new_id: str) -> int:
    with get_cursor() as (_, cur):
        cur.execute(
            """
            UPDATE chat_messages
            SET conversation_id = %s
            WHERE conversation_id = %s
            RETURNING id
            """,
            (new_id, old_id),
        )
        updated = cur.rowcount
        cur.execute(
            """
            UPDATE chatbot_leads_conversation
            SET conversation_id = %s
            WHERE conversation_id = %s
            """,
            (new_id, old_id),
        )
        cur.execute(
            """
            UPDATE chatbot_conversations
            SET conversation_id = %s
            WHERE conversation_id = %s
            """,
            (new_id, old_id),
        )
    return updated


def delete_conversation(conversation_id: str) -> Dict[str, int]:
    with get_cursor() as (_, cur):
        cur.execute(
            "DELETE FROM chatbot_leads_conversation WHERE conversation_id = %s",
            (conversation_id,),
        )
        leads_deleted = cur.rowcount
        cur.execute(
            "DELETE FROM chat_messages WHERE conversation_id = %s",
            (conversation_id,),
        )
        messages_deleted = cur.rowcount
        cur.execute(
            "DELETE FROM chatbot_conversations WHERE conversation_id = %s",
            (conversation_id,),
        )
    return {
        "leads_deleted": leads_deleted,
        "messages_deleted": messages_deleted,
    }
