from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class FormSubmissionRecord(BaseModel):
    id: int
    name: Optional[str]
    country: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    message: str
    source: str
    created_at: datetime
    notes: str
    status: str


class FormSubmissionUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class LeadRecord(BaseModel):
    id: int
    conversation_id: str
    phone: Optional[str]
    email: Optional[str]
    status: str
    notes: str
    ip: Optional[str]
    timestamp: datetime


class LeadUpdate(BaseModel):
    conversation_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    ip: Optional[str] = None
    timestamp: Optional[datetime] = None


class ConversationSummary(BaseModel):
    conversation_id: str
    started_at: datetime
    updated_at: datetime
    message_count: int
    last_role: Optional[str]
    last_message: Optional[str]
    last_ip: Optional[str]
    status: Optional[str]
    notes: Optional[str]


class ConversationMessage(BaseModel):
    id: int
    conversation_id: str
    created_at: datetime
    role: str
    content: str
    ip: Optional[str]
    status: Optional[str]
    notes: Optional[str]


class ConversationRename(BaseModel):
    target_conversation_id: str


class ConversationDeleteResponse(BaseModel):
    leads_deleted: int
    messages_deleted: int


class ConversationMetadataUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class PageMeta(BaseModel):
    total: int
    page: int
    size: int


class PaginatedFormSubmissions(BaseModel):
    data: List[FormSubmissionRecord]
    meta: PageMeta


class PaginatedLeadRecords(BaseModel):
    data: List[LeadRecord]
    meta: PageMeta


class PaginatedConversations(BaseModel):
    data: List[ConversationSummary]
    meta: PageMeta
