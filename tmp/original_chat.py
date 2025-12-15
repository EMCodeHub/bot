import re
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.llm.ollama_client import generate_response
from app.llm.embeddings import embed_query
from app.db.vector_store import find_texts_with_keywords, search_similar
from app.db.chat_history import (
    ensure_conversation_metadata,
    init_chat_history_table,
    init_chatbot_conversations_table,
    get_recent_messages,
    save_message,
)
from app.db.chatbot_leads_conversation import (
    init_chatbot_leads_conversation_table,
)
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Ensure chat_messages table exists when this module loads
init_chat_history_table()
init_chatbot_leads_conversation_table()
init_chatbot_conversations_table()


MAX_HISTORY_LINES = 4
MAX_CONTEXT_CHARS = 2200
MAX_CONTEXT_CHUNKS = 6
KEYWORD_MATCH_CHUNKS = 2
QUESTION_WORDS = {
    "quien",
    "quién",
    "quienes",
    "quiénes",
    "que",
    "qué",
    "como",
    "cómo",
    "cuando",
    "cuándo",
    "donde",
    "dónde",
    "por",
    "para",
    "cual",
    "cuál",
    "cuales",
    "cuáles",
    "cuanto",
    "cuánto",
    "cuantos",
    "cuántos",
    "cuanta",
    "cuánta",
}



def _extract_keywords(text: str):
    tokens = re.findall(r"[A-Za-z�-��-���0-9]+", text)
    keywords = []
    for token in tokens:
        normalized = token.strip().lower()
        if normalized in QUESTION_WORDS:
            continue
        if len(normalized) >= 5 or (token.isupper() and len(normalized) >= 3):
            keywords.append(normalized)
    return list(dict.fromkeys(keywords))


def _truncate(text: str, limit: int):
    if len(text) <= limit:
        return text
    return text[:limit]


def _truncate_history(text: str, limit: int):
    if len(text) <= limit:
        return text
    return text[-limit:]


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    # Determine conversation id
    conversation_id = req.conversation_id or str(uuid4())
    logger.info(f"/chat called, conv_id={conversation_id}")
    ensure_conversation_metadata(conversation_id)
    
    # Load recent history for this conversation (errors become empty history)
    try:
        history = get_recent_messages(conversation_id, limit=MAX_HISTORY_LINES)
    except Exception:
        logger.exception(f"Error loading history for conv={conversation_id}")
        history = []
    
    # Turn history into text for the prompt
    history_lines = []
    for msg in history:
        role = msg["role"]  # 'user' or 'assistant'
        prefix = "Usuario" if role == "user" else "Asistente"
        history_lines.append(f"{prefix}: {msg['content']}")
    history_lines = history_lines[-MAX_HISTORY_LINES:]
    history_text = "\n".join(history_lines) if history_lines else "(no previous messages)"
    history_text = _truncate_history(history_text, 800)

    # Get the last assistant reply so we avoid repeating it    
    last_assistant_reply = None
    for msg in reversed(history):
        if msg["role"] == "assistant":
            last_assistant_reply = msg["content"]
            break

    if last_assistant_reply:
        previous_answer_block = f"""
    Tu respuesta anterior fue:

    """
    {last_assistant_reply}
    """

   El usuario ha preguntado de nuevo o indicó que no entendió completamente.
No repitas la misma redacción ni estructura.
Explícalo de otra manera: con un lenguaje más simple, paso a paso o con ejemplos,
pero mantente preciso y alineado con el contexto.
    """
    else:
        previous_answer_block = ""

    # RAG: embed the user question and retrieve similar chunks
    try:
        q_embedding = embed_query(user_message)
        similar_chunks = search_similar(q_embedding, top_k=MAX_CONTEXT_CHUNKS)
    except Exception:
        logger.exception(f"Error during RAG (embedding/search_similar) for conv={conversation_id}")
        raise HTTPException(
            status_code=500,
            detail="Lo siento, hubo un problema buscando en nuestra base de conocimiento. Intenta nuevamente.",
        )

    keywords = _extract_keywords(user_message)
    keyword_chunks = []
    if keywords:
        keyword_chunks = find_texts_with_keywords(keywords, max_results=KEYWORD_MATCH_CHUNKS)

    context_chunks = [chunk["text"] for chunk in similar_chunks]
    for chunk in keyword_chunks:
        if chunk not in context_chunks:
            context_chunks.append(chunk)

    context = "\n\n".join(context_chunks)
    context = _truncate(context, MAX_CONTEXT_CHARS)

    final_prompt = f"""
    Eres el asistente oficial de Medifestructuras. Responde únicamente con la información proporcionada en el contexto y mantén las respuestas concisas.

Si no encuentras la respuesta dentro del contexto, indica claramente que no tienes la respuesta en este momento y sugiere al usuario revisar la página web www.medifestructuras.com
 o contactar al equipo correspondiente. También sugiere que el usuario proporcione un teléfono de contacto o correo electrónico.

Si el usuario se repite o indica que no entendió, reformula la respuesta con un lenguaje más simple, una estructura distinta o ejemplos útiles obtenidos del contexto, manteniendo la precisión.

Ante consultas sobre precios, asesorías o cursos, busca la información en el contexto. Tu función es ayudar y dar información, pero también conseguir el contacto telefónico o correo electrónico de la persona.

Si te preguntan quién eres, indica que eres el representante virtual del ingeniero Eduardo Mediavilla. Puedes indicar que este es nuestro teléfono de contacto: +357 96863257.

    {previous_answer_block}

    Conversaci�n hasta ahora:
    {history_text}

    CONTEXTO:
    {context}

    NUEVA PREGUNTA DEL USUARIO:
    {user_message}

    RESPUESTA:
    """.strip()

    try:
        answer = generate_response(final_prompt)
    except Exception:
        logger.exception(f"Error calling Ollama generate_response for conv={conversation_id}")
        raise HTTPException(
            status_code=500,
            detail="Hubo un problema al generar la respuesta. Por favor, inténtalo de nuevo.",
        )

    try:
        save_message(conversation_id, "user", user_message, ip=req.ip)
        save_message(conversation_id, "assistant", answer, ip=req.ip)
    except Exception:
        logger.exception(f"Failed to save messages for conv={conversation_id}")

    logger.info(f"/chat completed, conv_id={conversation_id}")
    return ChatResponse(response=answer, conversation_id=conversation_id)
