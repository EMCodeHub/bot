from typing import List

from fastapi import APIRouter, HTTPException, Path, Query

from app.db.chat_history import (
    list_conversation_messages,
    update_chat_message_metadata,
)
from app.models.chat_messages import (
    ChatMessageMetadataUpdate,
    ChatMessageOut,
)

router = APIRouter(prefix="/chat_messages", tags=["chat_messages"])


@router.get(
    "/",
    response_model=List[ChatMessageOut],
    summary="Listar todos los mensajes de una conversación",
)
def list_messages_for_conversation(conversation_id: str = Query(..., min_length=1)) -> List[ChatMessageOut]:
    """Devuelve todos los mensajes asociados al identificador de conversación suministrado."""
    return list_conversation_messages(conversation_id)


@router.patch(
    "/{message_id}",
    response_model=ChatMessageOut,
    summary="Actualizar metadatos de un mensaje de chat",
)
def update_message_metadata(
    message_id: int = Path(..., ge=1),
    payload: ChatMessageMetadataUpdate = ...,
) -> ChatMessageOut:
    """Permite al frontend guardar estado y notas para cada fila."""
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No se proporcionaron campos editables.")

    updated = update_chat_message_metadata(message_id, **updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")
    return updated
