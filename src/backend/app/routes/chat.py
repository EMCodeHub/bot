import asyncio
import os
import re
import unicodedata
from typing import List, Sequence
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.db.chat_history import (
    ensure_conversation_metadata,
    get_recent_messages,
    init_chat_history_table,
    init_chatbot_conversations_table,
    save_message,
)
from app.db.chatbot_leads_conversation import init_chatbot_leads_conversation_table
from app.db.vector_store import (
    find_texts_with_keywords,
    get_chunks_by_filepaths,
    search_similar,
)
from app.llm.embeddings import embed_query
from app.llm.ollama_client import generate_response
from app.models.chat import ChatRequest, ChatResponse
from app.utils.logger import get_logger
from app.utils.text import normalize_text

router = APIRouter()
logger = get_logger(__name__)

# Ensure chat_tables exist when this module loads
init_chat_history_table()
init_chatbot_leads_conversation_table()
init_chatbot_conversations_table()

MAX_HISTORY_LINES = 4
MAX_CONTEXT_CHARS = 2200
MAX_CONTEXT_CHUNKS = 8
CONTEXT_CHUNK_SEND_LIMIT = 5
KEYWORD_MATCH_CHUNKS = 2
SOURCE_INTENT_KEYWORDS = {
    "faq/": ("faq", "preguntas frecuentes", "pregunta frecuente"),
    "servicios/": ("servicio", "servicios", "contratar", "ofrecemos", "diseno", "proyecto"),
    "cursos/": ("curso", "cursos", "capacitacion", "formacion", "taller", "educacion"),
    "software/": ("software", "cype", "sap2000", "etabs", "modelacion", "cypeunext"),
}
COURSE_INTENT_KEYWORDS = {
    "curso",
    "cursos",
    "capacitacion",
    "formacion",
    "taller",
    "instalaciones",
    "instalacion",
}
COURSE_RESPONSE_GUIDELINES = (
    "Cuando la pregunta sea sobre cursos, confirma que Medif Estructuras ofrece 9 cursos en total "
    "(8 de estructuras y 1 de instalaciones), menciona primero esa visión general, luego describe un curso específico "
    "documentado en la base de conocimientos y cierra con el llamado a la acción sin negar cursos ni decir “no tengo información”."
)
COURSE_OVERVIEW_FILE = "overview_cursos.md"
MIN_CONTEXT_SIMILARITY = settings.rag_min_similarity
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
CONTACT_PROMPT = (
    "También podés hacer clic en “Enviar mis datos” o escribir tus datos en el chat "
    "para que coordinemos tu consulta, link de pago o llamada."
)
CONTACT_ACK = (
    "Gracias, hemos recibido tus datos y te contactaremos a la brevedad posible."
)

GREETING_KEYWORDS = {"hola", "buen", "buenas", "buenos", "saludos", "hey", "holi", "buen dia", "buen día", "qué tal", "como estas"}

def _looks_like_contact(message: str) -> bool:
    cleaned = message.replace(",", " ").replace(";", " ")
    has_email = any("@" in part and "." in part for part in cleaned.split())
    digits = "".join(ch for ch in message if ch.isdigit())
    has_phone = len(digits) >= 6
    return has_email or has_phone
QUESTION_WORDS = {
    "quien",
    "quienes",
    "que",
    "como",
    "cuando",
    "donde",
    "por",
    "para",
    "cual",
    "cuales",
    "cuanto",
    "cuantos",
    "cuanta",
    "cuantas",
    "porque",
}
SYSTEM_INSTRUCTIONS = (
    "Eres el asistente virtual oficial de Medifestructuras (www.medifestructuras.com). "
    "Responde siempre usando solo la informacion que aparece dentro del CONTEXTO y se muy conciso. "
    "Si no encuentras la respuesta en el CONTEXTO, deja claro que no la tienes y sugiere visitar "
    "la pagina web, escribir a eduardo.mediavilla@medifestructuras.com o llamar al +357 96863257. "
    "Evita inventar precios, cursos o servicios que no esten citados. "
    "Si el usuario vuelve a preguntar o dice que no entendio, reformula la respuesta con un lenguaje mas simple, ejemplos o pasos. "
    "El historial de la conversacion solo sirve para mantener el tono; no lo uses como fuente de hechos."
)
FALLBACK_RESPONSE = (
    "No tengo suficiente informacion en la base de conocimiento para responder eso. "
    "Por favor revisa www.medifestructuras.com o contactanos a eduardo.mediavilla@medifestructuras.com "
    "o por telefono al +357 96863257."
)


HUMAN_SOCIAL_RESPONSES = {

    
    "hola": "Hola, ¿cómo estás?",
    "holaa": "Hola, ¿cómo estás?",
    "holaaa": "Hola, ¿cómo estás?",
    "holaaaa": "Hola, ¿cómo estás?",
    "holaaaaa": "Hola, ¿cómo estás?",
    "holi": "Hola, ¿cómo estás?",
    "holis": "Hola, ¿cómo estás?",
    "holita": "Hola, ¿cómo estás?",
    "ola": "Hola, ¿cómo estás?",
    "olaa": "Hola, ¿cómo estás?",
    "olaas": "Hola, ¿cómo estás?",
    "hello": "Hola, ¿cómo estás?",
    "hey": "Hola, ¿cómo estás?",
    "hey!": "Hola, ¿cómo estás?",
    "ey": "Hola, ¿cómo estás?",
    "eyy": "Hola, ¿cómo estás?",
    "buenas": "Hola, ¿cómo estás?",
    "buenass": "Hola, ¿cómo estás?",
    "buenas!": "Hola, ¿cómo estás?",
    "buenas buenas": "Hola, ¿cómo estás?",


    "buenos dias": "Buenos días, ¿en qué te puedo ayudar?",
    "buenos días": "Buenos días, ¿en qué te puedo ayudar?",
    "buen dia": "Buenos días, ¿en qué te puedo ayudar?",
    "buen día": "Buenos días, ¿en qué te puedo ayudar?",
    "buenos diass": "Buenos días, ¿en qué te puedo ayudar?",
    "bd": "Buenos días, ¿en qué te puedo ayudar?",
    "b dias": "Buenos días, ¿en qué te puedo ayudar?",
    "buen díaa": "Buenos días, ¿en qué te puedo ayudar?",

    
    "buenas tardes": "Buenas tardes, ¿en qué te ayudo?",
    "buenas tardess": "Buenas tardes, ¿en qué te ayudo?",
    "bt": "Buenas tardes, ¿en qué te ayudo?",
    "b tardes": "Buenas tardes, ¿en qué te ayudo?",
    "tardes": "Buenas tardes, ¿en qué te ayudo?",

    "buenas noches": "Buenas noches, ¿en qué puedo ayudarte?",
    "buenas nochess": "Buenas noches, ¿en qué puedo ayudarte?",
    "bn": "Buenas noches, ¿en qué puedo ayudarte?",
    "noches": "Buenas noches, ¿en qué puedo ayudarte?",

    
    "que tal": "Hola, ¿cómo estás?",
    "qué tal": "Hola, ¿cómo estás?",
    "q tal": "Hola, ¿cómo estás?",
    "como estas": "Hola, ¿cómo estás?",
    "como estás": "Hola, ¿cómo estás?",
    "como estas?": "Hola, ¿cómo estás?",
    "como andas": "Hola, ¿cómo estás?",
    "como vas": "Hola, ¿cómo estás?",
    "todo bien": "¡Genial! ¿En qué te puedo ayudar?",
    "todo ok": "¡Genial! ¿En qué te puedo ayudar?",
    "todo bien?": "¡Genial! ¿En qué te puedo ayudar?",
    "todo tranqui": "¡Perfecto! ¿En qué te ayudo?",

    
    "que onda": "Hola, ¿cómo estás?",
    "qué onda": "Hola, ¿cómo estás?",
    "onda": "Hola, ¿cómo estás?",
    "que mas": "Hola, ¿cómo estás?",
    "qué más": "Hola, ¿cómo estás?",
    "que mas pues": "Hola, ¿cómo estás?",
    "que hubo": "Hola, ¿cómo estás?",
    "quiubo": "Hola, ¿cómo estás?",
    "parce": "Hola, ¿cómo estás?",
    "parcero": "Hola, ¿cómo estás?",
    "wey": "Hola, ¿cómo estás?",
    "weyy": "Hola, ¿cómo estás?",
    "che": "Hola, ¿cómo estás?",
    "amigo": "Hola, ¿cómo estás?",

    
    "qué pasa": "Hola, ¿cómo estás?",
    "que pasa": "Hola, ¿cómo estás?",
    "todo bien tio": "Hola, ¿cómo estás?",
    "buenas tio": "Hola, ¿cómo estás?",
    "vale": "Perfecto, quedo atento.",
    "ok vale": "Perfecto, quedo atento.",


    "gracias": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "graciass": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "gracias!": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "muchas gracias": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "mil gracias": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "gracias totales": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "thanks": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "ok gracias": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "gracias amigo": "¡Con gusto! Si necesitas algo más, aquí estaré.",
    "gracias bro": "¡Con gusto! Si necesitas algo más, aquí estaré.",


    "ok": "Perfecto, quedo atento.",
    "okey": "Perfecto, quedo atento.",
    "oki": "Perfecto, quedo atento.",
    "okis": "Perfecto, quedo atento.",
    "perfecto": "Perfecto, quedo atento.",
    "excelente": "Perfecto, quedo atento.",
    "genial": "Perfecto, quedo atento.",
    "de acuerdo": "Perfecto, quedo atento.",
    "entendido": "Perfecto, gracias por avisar.",
    "listo": "Perfecto, quedo atento.",
    "dale": "Perfecto, quedo atento.",
    "va": "Perfecto, quedo atento.",
    "bien": "Perfecto, quedo atento.",

    
    "chau": "¡Hasta luego! 😊",
    "chao": "¡Hasta luego! 😊",
    "adios": "¡Hasta luego! 😊",
    "adiós": "¡Hasta luego! 😊",
    "nos vemos": "¡Hasta luego! 😊",
    "hasta luego": "¡Hasta luego! 😊",
    "hasta pronto": "¡Hasta pronto! 😊",
    "bye": "¡Hasta luego! 😊",
    "bye bye": "¡Hasta luego! 😊",
}







COURTESY_PATTERNS = [
    (["agradecid"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["agradecid", "respuesta"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["muchas", "gracias"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["con", "gusto"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias", "👏"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["muchisimas", "gracias"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias", "por", "todo"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias", "de", "nuevo"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["que", "pase", "buen", "dia"], "Que tengas un excelente día."),
    (["pase", "buen", "dia"], "Que tengas un excelente día."),
    (["que", "este", "bien"], "Que estés muy bien."),
    (["que", "este", "muy"], "Que estés muy bien."),
    (["todo", "claro"], HUMAN_SOCIAL_RESPONSES["perfecto"]),
    (["perfecto", "gracias"], HUMAN_SOCIAL_RESPONSES["perfecto"]),
    (["perfecto"], HUMAN_SOCIAL_RESPONSES["perfecto"]),
    (["excelente"], HUMAN_SOCIAL_RESPONSES["excelente"]),
    (["genial"], HUMAN_SOCIAL_RESPONSES["perfecto"]),
    (["gracias", "por", "la", "info"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias", "por", "todo", "amigo"], HUMAN_SOCIAL_RESPONSES["gracias"]),
    (["gracias", "de", "corazón"], HUMAN_SOCIAL_RESPONSES["gracias"]),
]

INFORMATIVE_MARKERS = {
    "precio",
    "costo",
    "cuesta",
    "curso",
    "servicio",
    "informacion",
    "detalle",
    "solicito",
    "saber",
    "necesito",
    "puedo",
    "puedes",
    "instalar",
    "disenar",
    "diseno",
    "calcular",
    "cotizacion",
    "presupuesto",
    "proyecto",
    "consulta",
    "contacto",
    "telefono",
    "email",
    "correo",
}

def _normalize_social_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    cleaned = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"(.)\1+", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _matches_courtesy_pattern(message: str, normalized: str) -> str | None:
    if "?" in message or "¿" in message:
        return None
    if any(marker in normalized for marker in INFORMATIVE_MARKERS):
        return None
    for keywords, response in COURTESY_PATTERNS:
        if all(keyword in normalized for keyword in keywords):
            return response
    return None


def _detect_social_response_extended(message: str) -> str | None:
    normalized = _normalize_social_text(message)
    response = HUMAN_SOCIAL_RESPONSES.get(normalized)
    if response:
        return response
    return _matches_courtesy_pattern(message, normalized)


def _append_contact_prompt(answer: str) -> str:
    stripped = answer.strip()
    if not stripped:
        return CONTACT_PROMPT
    if CONTACT_PROMPT in stripped:
        return stripped
    punctuation = "." if stripped[-1] not in ".!?" else ""
    return f"{stripped}{punctuation} {CONTACT_PROMPT}"


def _extract_keywords(text: str) -> List[str]:
    tokens = TOKEN_PATTERN.findall(text)
    keywords = []
    for token in tokens:
        normalized = token.strip().lower()
        if not normalized or normalized in QUESTION_WORDS:
            continue
        if len(normalized) >= 5 or (token.isupper() and len(normalized) >= 3):
            keywords.append(normalized)
    return list(dict.fromkeys(keywords))


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]


def _truncate_history(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _format_history(history: List[dict]) -> tuple[str, str | None]:
    history_lines = []
    last_assistant_reply = None
    for msg in history[-MAX_HISTORY_LINES:]:
        role = msg.get("role")
        prefix = "Usuario" if role == "user" else "Asistente"
        history_lines.append(f"{prefix}: {msg.get('content', '').strip()}")
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            last_assistant_reply = msg.get("content")
            break
    history_text = "\n".join(history_lines) if history_lines else "(no previous messages)"
    return _truncate_history(history_text, 800), last_assistant_reply


def _build_previous_answer_block(last_assistant_reply: str | None) -> str:
    if not last_assistant_reply:
        return ""
    return (
        "Tu respuesta anterior fue:\n"
        '"""\n'
        f"{last_assistant_reply.strip()}\n"
        '"""\n'
        "El usuario volvio a consultar o indico que no entendio. "
        "No repitas la misma redaccion ni estructura; explicalo con lenguaje mas simple, pasos o ejemplos, pero mantente preciso."
    )


def _dot_product(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def _is_course_request(normalized_message: str) -> bool:
    return any(keyword in normalized_message for keyword in COURSE_INTENT_KEYWORDS)

def _infer_source_filters(normalized_message: str) -> list[str]:
    matches = []
    for prefix, keywords in SOURCE_INTENT_KEYWORDS.items():
        if any(keyword in normalized_message for keyword in keywords):
            matches.append(prefix)
    return matches

def _chunk_priority(source: str | None) -> int:
    if not source:
        return 3
    basename = os.path.basename(source).lower()
    if basename == "routing.md":
        return 0
    if basename.endswith("_summary.md") or basename == "faq.md":
        return 1
    if basename.startswith("faq_") and basename.endswith(".md"):
        return 1
    return 2

def _select_context_chunks(chunks: List[dict], limit: int) -> List[str]:
    candidates = [
        chunk for chunk in chunks if chunk.get("text")
    ]
    sorted_chunks = sorted(
        candidates,
        key=lambda chunk: (_chunk_priority(chunk.get("source")), -chunk.get("similarity", 0.0)),
    )
    selected = []
    seen_sources = set()
    seen_texts = set()
    for chunk in sorted_chunks:
        if len(selected) >= limit:
            break
        text = chunk["text"].strip()
        if not text:
            continue
        source = chunk.get("source", "") or ""
        normalized_text = normalize_text(text).lower()
        if source in seen_sources or normalized_text in seen_texts:
            continue
        selected.append(text)
        seen_sources.add(source)
        seen_texts.add(normalized_text)
    return selected


def _validate_keyword_chunks(
    query_embedding: List[float], keywords: List[str], existing_texts: set[str]
) -> List[str]:
    if not keywords:
        return []
    validated = []
    candidate_texts = find_texts_with_keywords(keywords, max_results=KEYWORD_MATCH_CHUNKS)
    for text in candidate_texts:
        normalized_candidate = text.strip()
        if not normalized_candidate:
            continue
        normalized_lower = normalize_text(normalized_candidate).lower()
        if not normalized_lower or normalized_lower in existing_texts:
            continue
        try:
            chunk_embedding = embed_query(normalized_candidate)
        except Exception as exc:
            logger.exception("Error embedding keyword chunk: %s", exc)
            continue
        similarity = _dot_product(query_embedding, chunk_embedding)
        if similarity >= MIN_CONTEXT_SIMILARITY:
            validated.append(normalized_candidate)
            existing_texts.add(normalized_lower)
    return validated


def _retrieve_context(
    user_message: str,
    keywords: List[str],
    normalized_message: str | None = None,
    course_intent: bool = False,
) -> dict:
    query_embedding = embed_query(user_message)
    normalized_for_filters = normalized_message or _normalize_social_text(user_message)
    source_filters = _infer_source_filters(normalized_for_filters)
    similar_chunks = search_similar(
        query_embedding,
        top_k=MAX_CONTEXT_CHUNKS,
        source_prefixes=source_filters or None,
    )
    valid_chunks = [
        chunk for chunk in similar_chunks if chunk.get("similarity", 0.0) >= MIN_CONTEXT_SIMILARITY
    ]
    best_similarity = max((chunk.get("similarity", 0.0) for chunk in valid_chunks), default=0.0)
    selected_chunks = _select_context_chunks(valid_chunks, CONTEXT_CHUNK_SEND_LIMIT)
    context_chunks: List[str] = []
    dedup_texts: set[str] = set()

    if course_intent:
        overview_chunks = get_chunks_by_filepaths((COURSE_OVERVIEW_FILE,))
        for chunk in overview_chunks:
            overview_text = chunk.get("text", "").strip()
            if not overview_text:
                continue
            normalized_overview = normalize_text(overview_text).lower()
            if normalized_overview in dedup_texts:
                continue
            context_chunks.append(overview_text)
            dedup_texts.add(normalized_overview)
            break

    for chunk_text in selected_chunks:
        if len(context_chunks) >= CONTEXT_CHUNK_SEND_LIMIT:
            break
        normalized_chunk = normalize_text(chunk_text).lower()
        if not normalized_chunk or normalized_chunk in dedup_texts:
            continue
        context_chunks.append(chunk_text)
        dedup_texts.add(normalized_chunk)

    keyword_chunks = _validate_keyword_chunks(query_embedding, keywords, dedup_texts)
    for keyword_chunk in keyword_chunks:
        if len(context_chunks) >= CONTEXT_CHUNK_SEND_LIMIT:
            break
        trimmed = keyword_chunk.strip()
        if not trimmed:
            continue
        normalized_keyword = normalize_text(trimmed).lower()
        if not normalized_keyword or normalized_keyword in dedup_texts:
            continue
        context_chunks.append(trimmed)
        dedup_texts.add(normalized_keyword)

    return {
        "query_embedding": query_embedding,
        "similar_chunks": len(valid_chunks),
        "keyword_chunks": len(keyword_chunks),
        "best_similarity": best_similarity,
        "context_chunks": context_chunks,
        "source_filters": source_filters or [],
        "used_chunks": len(context_chunks),
    }


def _build_prompt(
    previous_answer_block: str,
    history_text: str,
    context: str,
    user_message: str,
    course_instruction: str | None = None,
) -> str:
    sections = [
        SYSTEM_INSTRUCTIONS,
        course_instruction,
        previous_answer_block,
        f"Conversacion hasta ahora:\n{history_text}",
        f"CONTEXTO:\n{context}",
        f"NUEVA PREGUNTA DEL USUARIO:\n{user_message}",
        "RESPUESTA:",
    ]
    return "\n\n".join(section for section in sections if section).strip()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    user_message = req.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio.")
    normalized_message = _normalize_social_text(user_message)
    course_intent = _is_course_request(normalized_message)

    conversation_id = req.conversation_id or str(uuid4())
    logger.info("/chat called, conv_id=%s question=%s", conversation_id, user_message[:100])
    ensure_conversation_metadata(conversation_id)

    if _looks_like_contact(user_message):
        logger.info("Contact info received for conv=%s", conversation_id)
        response = _append_contact_prompt(CONTACT_ACK)
        await asyncio.sleep(1.5)
        try:
            save_message(conversation_id, "user", user_message, ip=req.ip)
            save_message(conversation_id, "assistant", response, ip=req.ip)
        except Exception:
            logger.exception("Failed to save contact info exchange for conv=%s", conversation_id)
        return ChatResponse(response=response, conversation_id=conversation_id)

    short_response = _detect_social_response(user_message)
    if short_response:
        logger.info("Short-circuit social message for conv=%s", conversation_id)
        await asyncio.sleep(7.0)
        is_greeting = normalized_message in GREETING_KEYWORDS
        try:
            save_message(conversation_id, "user", user_message, ip=req.ip)
            assistant_response = short_response if is_greeting else _append_contact_prompt(short_response)
            save_message(conversation_id, "assistant", assistant_response, ip=req.ip)
        except Exception:
            logger.exception("Failed to save short social exchange for conv=%s", conversation_id)
        return ChatResponse(response=assistant_response, conversation_id=conversation_id)

    try:
        history = get_recent_messages(conversation_id, limit=MAX_HISTORY_LINES)
    except Exception:
        logger.exception("Error loading history for conv=%s", conversation_id)
        history = []

    history_text, last_assistant_reply = _format_history(history)
    previous_answer_block = _build_previous_answer_block(last_assistant_reply)

    keywords = _extract_keywords(user_message)
    try:
        rag_result = _retrieve_context(
            user_message,
            keywords,
            normalized_message,
            course_intent=course_intent,
        )
    except Exception:
        logger.exception("Error during RAG (embedding/search_similar) for conv=%s", conversation_id)
        raise HTTPException(
            status_code=500,
            detail="Lo siento, hubo un problema buscando en nuestra base de conocimiento. Intenta nuevamente.",
        )

    context_chunks = rag_result["context_chunks"]
    logger.info(
        "RAG conv=%s filters=%s retrieved=%d used=%d keywords=%d best_similarity=%.3f threshold=%.2f",
        conversation_id,
        ",".join(rag_result["source_filters"]) or "all",
        rag_result["similar_chunks"],
        rag_result["used_chunks"],
        rag_result["keyword_chunks"],
        rag_result["best_similarity"],
        MIN_CONTEXT_SIMILARITY,
    )

    if not context_chunks:
        logger.warning("No context available for conv=%s, skipping generation", conversation_id)
        answer = FALLBACK_RESPONSE
    else:
        context = _truncate("\n\n".join(context_chunks), MAX_CONTEXT_CHARS)
        prompt = _build_prompt(
            previous_answer_block,
            history_text,
            context,
            user_message,
            course_instruction=COURSE_RESPONSE_GUIDELINES if course_intent else None,
        )
        try:
            answer = generate_response(
                prompt,
                temperature=settings.ollama_temperature,
                top_p=settings.ollama_top_p,
            )
        except Exception:
            logger.exception("Error calling Ollama generate_response for conv=%s", conversation_id)
            raise HTTPException(
                status_code=500,
                detail="Hubo un problema al generar la respuesta. Por favor, intentalo de nuevo.",
            )

    try:
        save_message(conversation_id, "user", user_message, ip=req.ip)
        final_answer = _append_contact_prompt(answer)
        save_message(conversation_id, "assistant", final_answer, ip=req.ip)
    except Exception:
        logger.exception("Failed to save messages for conv=%s", conversation_id)

    logger.info(
        "/chat completed, conv_id=%s context_used=%s",
        conversation_id,
        bool(context_chunks),
    )
    return ChatResponse(response=final_answer, conversation_id=conversation_id)
# override with extended detection
_detect_social_response = _detect_social_response_extended
