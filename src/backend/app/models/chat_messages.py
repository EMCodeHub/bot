from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatMessageOut(BaseModel):
    id: int
    conversation_id: str
    created_at: datetime
    role: str
    content: str
    ip: Optional[str]
    status: Optional[str]
    notes: Optional[str]


class ChatMessageMetadataUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
