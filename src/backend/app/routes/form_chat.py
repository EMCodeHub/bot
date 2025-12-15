from fastapi import APIRouter, HTTPException

from app.db.form_chatbot import init_form_chatbot_table, save_form_submission
from app.models.form_chatbot import FormChatbotPayload
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Ensure the form_chatbot table exists as soon as this router is imported.
init_form_chatbot_table()


@router.post("/chatform", status_code=201)
def submit_form(payload: FormChatbotPayload):
    """
    Accept submissions that mirror the existing /chat payload and persist them.
    """
    logger.info("Received chat form submission for source=%s", payload.source)
    try:
        submission_id = save_form_submission(payload)
    except Exception:
        logger.exception("Failed to persist chat form submission")
        raise HTTPException(
            status_code=500,
            detail="No pudimos guardar la solicitud del formulario de chat. Intenta nuevamente más tarde.",
        )
    return {"id": submission_id}
