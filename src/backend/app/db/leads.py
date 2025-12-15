from psycopg2.extras import RealDictCursor, Json
from typing import Optional, Dict, Any

from app.db.postgres import get_cursor
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_lead(
    name: Optional[str],
    company: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    message: Optional[str],
    source: str = "chatbot",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Insert a new lead into the leads table.
    Returns the new lead id.
    """
    sql = """
        INSERT INTO leads (name, company, email, phone, message, source, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    metadata = Json(metadata) if metadata is not None else None
    with get_cursor(cursor_factory=RealDictCursor) as (_, cur):
        cur.execute(
            sql,
            (name, company, email, phone, message, source, metadata),
        )
        row = cur.fetchone()
        lead_id = row["id"]
        logger.info(f"Lead created successfully id={lead_id}, email={email}")
        return lead_id
