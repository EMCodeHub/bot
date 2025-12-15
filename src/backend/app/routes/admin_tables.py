from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.db.admin_tables import (
    delete_chatbot_lead,
    delete_conversation,
    delete_form_submission,
    get_chatbot_lead,
    get_conversation_summary,
    get_form_submission,
    list_chatbot_leads,
    list_conversation_messages,
    list_conversations,
    list_form_submissions,
    rename_conversation,
    update_chatbot_lead,
    update_conversation_metadata,
    update_form_submission,
)
from app.models.admin import (
    ConversationDeleteResponse,
    ConversationMessage,
    ConversationMetadataUpdate,
    ConversationRename,
    ConversationSummary,
    FormSubmissionRecord,
    FormSubmissionUpdate,
    LeadRecord,
    LeadUpdate,
    PageMeta,
    PaginatedConversations,
    PaginatedFormSubmissions,
    PaginatedLeadRecords,
)
router = APIRouter(tags=["admin"])


# --- form_chatbot --------------------------------------------------------------------------

@router.get(
    "/form_chatbot",
    response_model=PaginatedFormSubmissions,
    summary="List stored chatbot form submissions",
)
def list_form_chatbot_submissions(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
) -> PaginatedFormSubmissions:
    """Return paginated rows from the `form_chatbot` table."""
    limit = size
    offset = (page - 1) * size
    rows, total = list_form_submissions(limit=limit, offset=offset)
    return PaginatedFormSubmissions(
        data=rows,
        meta=PageMeta(total=total, page=page, size=size),
    )


@router.get(
    "/form_chatbot/{submission_id}",
    response_model=FormSubmissionRecord,
    summary="Fetch a single form submission",
)
def get_form_submission_by_id(submission_id: int = Path(..., ge=1)) -> FormSubmissionRecord:
    """Retrieve a row from `form_chatbot` by its primary key."""
    row = get_form_submission(submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Form submission not found.")
    return row


@router.put(
    "/form_chatbot/{submission_id}",
    response_model=FormSubmissionRecord,
    summary="Update a stored form submission",
)
def update_form_submission_by_id(
    submission_id: int = Path(..., ge=1),
    payload: FormSubmissionUpdate = ...,
) -> FormSubmissionRecord:
    """Update editable columns in `form_chatbot`. Only provided fields are changed."""
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields were provided.")
    updated = update_form_submission(submission_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Form submission not found or not updated.")
    return updated


@router.delete(
    "/form_chatbot/{submission_id}",
    status_code=204,
    summary="Delete a form submission",
)
def delete_form_submission_by_id(submission_id: int = Path(..., ge=1)) -> None:
    """Remove a row from `form_chatbot`. Returns 404 if the record doesn't exist."""
    deleted = delete_form_submission(submission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Form submission not found.")


# --- chatbot_leads_conversation --------------------------------------------------------------

@router.get(
    "/chatbot_leads_conversation",
    response_model=PaginatedLeadRecords,
    summary="List captured leads",
)
def list_chatbot_leads_endpoint(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
) -> PaginatedLeadRecords:
    """Return lead rows ordered by timestamp."""
    limit = size
    offset = (page - 1) * size
    rows, total = list_chatbot_leads(limit=limit, offset=offset)
    return PaginatedLeadRecords(
        data=rows,
        meta=PageMeta(total=total, page=page, size=size),
    )


@router.get(
    "/chatbot_leads_conversation/{lead_id}",
    response_model=LeadRecord,
    summary="Fetch a lead entry",
)
def get_chatbot_lead_by_id(lead_id: int = Path(..., ge=1)) -> LeadRecord:
    """Retrieve a single lead by its primary key."""
    lead = get_chatbot_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    return lead


@router.put(
    "/chatbot_leads_conversation/{lead_id}",
    response_model=LeadRecord,
    summary="Update a lead entry",
)
def update_chatbot_lead_by_id(
    lead_id: int = Path(..., ge=1),
    payload: LeadUpdate = ...,
) -> LeadRecord:
    """Update allowed columns on the `chatbot_leads_conversation` table."""
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No editable fields were provided.")
    updated = update_chatbot_lead(lead_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found or not updated.")
    return updated


@router.delete(
    "/chatbot_leads_conversation/{lead_id}",
    status_code=204,
    summary="Delete a lead",
)
def delete_chatbot_lead_by_id(lead_id: int = Path(..., ge=1)) -> None:
    """Remove a lead from `chatbot_leads_conversation`. Returns 404 if missing."""
    deleted = delete_chatbot_lead(lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lead not found.")


# --- chatbot_conversations ------------------------------------------------------------------

@router.get(
    "/chatbot_conversations",
    response_model=PaginatedConversations,
    summary="List available conversations",
)
def list_chatbot_conversations_endpoint(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=1000),
) -> PaginatedConversations:
    """Return basic metadata for each conversation stored in `chat_messages`."""
    limit = size
    offset = (page - 1) * size
    rows, total = list_conversations(limit=limit, offset=offset)
    return PaginatedConversations(
        data=rows,
        meta=PageMeta(total=total, page=page, size=size),
    )


@router.get(
    "/chatbot_conversations/{conversation_id}",
    response_model=List[ConversationMessage],
    summary="Fetch every message for a conversation",
)
def get_chatbot_conversation_details(conversation_id: str) -> List[ConversationMessage]:
    """Return all messages that belong to a conversation, ordered by creation time."""
    summary = get_conversation_summary(conversation_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return list_conversation_messages(conversation_id)


@router.patch(
    "/chatbot_conversations/{conversation_id}/metadata",
    response_model=ConversationSummary,
    summary="Update conversation metadata",
)
def update_chatbot_conversation_metadata(
    conversation_id: str, payload: ConversationMetadataUpdate
) -> ConversationSummary:
    """Set status/notes for a stored conversation."""
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No metadata keys provided.")
    update_conversation_metadata(conversation_id, updates)
    summary = get_conversation_summary(conversation_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return summary


@router.put(
    "/chatbot_conversations/{conversation_id}",
    response_model=ConversationSummary,
    summary="Rename a conversation",
)
def rename_chatbot_conversation(
    conversation_id: str,
    payload: ConversationRename,
) -> ConversationSummary:
    """Update the `conversation_id` used by every message (and lead) in the conversation."""
    if conversation_id == payload.target_conversation_id:
        raise HTTPException(status_code=400, detail="Target conversation ID must differ from the current one.")
    updated = rename_conversation(conversation_id, payload.target_conversation_id)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    summary = get_conversation_summary(payload.target_conversation_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Conversation not found after rename.")
    return summary


@router.delete(
    "/chatbot_conversations/{conversation_id}",
    response_model=ConversationDeleteResponse,
    summary="Remove a conversation and its leads",
)
def delete_chatbot_conversation(conversation_id: str) -> ConversationDeleteResponse:
    """Delete all messages and leads for a specific conversation."""
    result = delete_conversation(conversation_id)
    if result["messages_deleted"] == 0 and result["leads_deleted"] == 0:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return ConversationDeleteResponse(**result)
