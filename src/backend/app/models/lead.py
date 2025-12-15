from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any


class LeadCreate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    message: Optional[str] = None   # what they’re interested in
    source: str = "chatbot"         # default value
    metadata: Optional[Dict[str, Any]] = None
