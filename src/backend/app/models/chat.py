from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    # system_prompt: Optional[str] = None   # this can be added later for mroe specific (e.g per page) prompts
    # Which conversation this message belongs to.
    # If None, backend can create a new conversation_id.
    conversation_id: Optional[str] = None
    ip: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    # The conversation id the backend used.
    # Frontend should store this and send it back next time.
    conversation_id: str
