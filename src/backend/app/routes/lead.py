# src/backend/app/routes/lead.py
from fastapi import APIRouter, HTTPException

from app.models.lead import LeadCreate
from app.db.leads import create_lead
from app.utils.logger import get_logger

router = APIRouter(prefix="/leads", tags=["leads"])
logger = get_logger(__name__)


@router.post("/", status_code=201)
def create_lead_endpoint(payload: LeadCreate):
    if not payload.email and not payload.phone:
        raise HTTPException(
            status_code=400,
            detail="At least an email or a phone number is required.",
        )

    try:
        lead_id = create_lead(
            name=payload.name,
            company=payload.company,
            email=str(payload.email) if payload.email else None,
            phone=payload.phone,
            message=payload.message,
            source=payload.source,
            metadata=payload.metadata,
        )
    except Exception:
        logger.exception(
            "Error while creating lead from payload: "
            f"name={payload.name}, email={payload.email}"
        )
        raise HTTPException(
            status_code=500,
            detail="We couldn't save your contact details. Please try again later.",
        )

    return {"id": lead_id}
