from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FormChatbotPayload(BaseModel):
    name: str
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    message: str
    source: str = "medtl_chat_widget"
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    notes: Optional[str] = None
    status: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
