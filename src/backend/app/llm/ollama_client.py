import json
import time
from typing import Any

import requests
from requests import HTTPError, RequestException

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaRequestError(RuntimeError):
    """Represents a failed HTTP call against the Ollama API."""

    def __init__(self, endpoint: str, status_code: int | None = None, detail: str | None = None):
        detail = detail or "Ollama request failed without details."
        message = f"Ollama {endpoint} error"
        if status_code:
            message += f" (status={status_code})"
        super().__init__(detail)
        self.endpoint = endpoint
        self.status_code = status_code
        self.detail = detail


def _ollama_url(endpoint: str) -> str:
    base = settings.ollama_base_url.rstrip("/")
    return f"{base}{endpoint}"


def _should_retry(status_code: int | None) -> bool:
    if status_code is None:
        return True
    return status_code >= 500


def _post_to_ollama(endpoint: str, payload: dict, timeout: float) -> dict[str, Any]:
    url = _ollama_url(endpoint)
    last_error: OllamaRequestError | None = None
    for attempt in range(settings.ollama_http_retries):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=(settings.ollama_connect_timeout, timeout),
            )
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            status_code = exc.response.status_code if exc.response else None
            detail = exc.response.text if exc.response else str(exc)
            last_error = OllamaRequestError(endpoint, status_code, detail)
            logger.warning(
                "Ollama %s returned %s; detail=%s",
                endpoint,
                status_code,
                detail.strip(),
            )
            if not _should_retry(status_code):
                break
        except RequestException as exc:
            detail = str(exc)
            last_error = OllamaRequestError(endpoint, None, detail)
            logger.warning("Network failure when calling Ollama %s: %s", endpoint, detail)
        if attempt < settings.ollama_http_retries - 1:
            backoff = settings.ollama_retry_backoff * (attempt + 1)
            logger.debug(
                "Retrying Ollama %s (attempt %d/%d) after %.1fs",
                endpoint,
                attempt + 1,
                settings.ollama_http_retries,
                backoff,
            )
            time.sleep(backoff)
    if last_error:
        logger.error(
            "Ollama %s failed after %d attempts: %s",
            endpoint,
            settings.ollama_http_retries,
            last_error.detail,
        )
        raise last_error
    raise OllamaRequestError(endpoint, detail="Failed to connect to Ollama.")


def request_embedding_vector(text: str) -> list[float]:
    payload = {
        "model": settings.ollama_embed_model,
        "prompt": text,
    }
    data = _post_to_ollama("/api/embeddings", payload, settings.ollama_timeout)
    embedding = data.get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError(f"Ollama response missing embedding: {data}")
    return embedding


def _extract_message_content(data: dict[str, Any]) -> str:
    message = data.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    return ""


def _extract_generated_text(data: dict[str, Any]) -> str:
    for key in ("response", "generated_text", "text", "completion", "result"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    choices = data.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            for field in ("content", "text", "message"):
                content = choice.get(field)
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return ""


def _resolve_model_response_text(data: dict[str, Any]) -> str:
    content = _extract_message_content(data)
    if content:
        return content
    return _extract_generated_text(data)


def _payload_brief(data: dict[str, Any]) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(data)


def generate_response(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    model_name = model or settings.ollama_chat_model
    temp = temperature if temperature is not None else settings.ollama_temperature
    selected_top_p = top_p if top_p is not None else settings.ollama_top_p
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        "top_p": selected_top_p,
        "stream": False,
    }
    data = _post_to_ollama("/api/chat", payload, settings.ollama_generate_timeout)
    if "error" in data:
        error_value = data["error"]
        detail = (
            error_value.get("message")
            if isinstance(error_value, dict)
            else str(error_value)
        )
        raise OllamaRequestError(
            "/api/chat",
            detail=detail or f"Ollama error payload: {_payload_brief(data)}",
        )
    text = _resolve_model_response_text(data)
    if not text:
        payload_brief = _payload_brief(data)
        logger.warning("Ollama chat response missing text payload: %s", payload_brief)
        if data.get("done"):
            raise OllamaRequestError(
                "/api/chat",
                detail=f"Ollama chat replied without text: {payload_brief}",
                status_code=None,
            )
        return ""
    return text


def _ping_base_url() -> tuple[bool, str]:
    url = settings.ollama_base_url
    try:
        response = requests.get(url, timeout=settings.ollama_health_timeout)
        response.raise_for_status()
        return True, "Ollama base URL reachable"
    except RequestException as exc:
        detail = str(exc)
        logger.warning("Failed to reach Ollama base URL: %s", detail)
        return False, detail


def _safe_health_call(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"endpoint": endpoint, "ok": False}
    try:
        _post_to_ollama(endpoint, payload, settings.ollama_health_timeout)
        result["ok"] = True
        result["detail"] = "ok"
        return result
    except OllamaRequestError as exc:
        result["status_code"] = exc.status_code
        result["detail"] = exc.detail
        return result


def get_ollama_health() -> dict[str, Any]:
    reachable, detail = _ping_base_url()
    health = {"reachable": reachable, "detail": detail}
    if not reachable:
        return health

    health["embedding"] = _safe_health_call(
        "/api/embeddings",
        {"model": settings.ollama_embed_model, "prompt": "ping"},
    )
    health["chat"] = _safe_health_call(
        "/api/chat",
        {
            "model": settings.ollama_chat_model,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0.0,
            "top_p": 1.0,
            "stream": False,
        },
    )
    return health
