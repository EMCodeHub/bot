import requests
from typing import Sequence, Tuple

from app.config import settings

def _format_url(endpoint: str) -> str:
    base = settings.ollama_url.rstrip("/")
    return f"{base}{endpoint}"

def _call_ollama_endpoint(
    endpoint_payloads: Sequence[Tuple[str, dict]], timeout: float
) -> dict:
    errors: list[str] = []
    for endpoint, payload in endpoint_payloads:
        url = _format_url(endpoint)
        try:
            response = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            raise RuntimeError(f"Error calling Ollama {endpoint}: {exc}") from exc
        if response.status_code == 404:
            errors.append(f"{endpoint}=404")
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"Ollama {endpoint} failed with status {response.status_code}"
            ) from exc
        return response.json()
    attempted = ", ".join(endpoint for endpoint, _ in endpoint_payloads)
    status_info = ", ".join(errors) if errors else "no responses"
    raise RuntimeError(
        "None of the Ollama endpoints responded successfully "
        f"(tried {attempted}; {status_info})."
    )

def _filter_vector_candidate(raw: object) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        for key in ("data", "values", "vector", "embedding"):
            candidate = raw.get(key)  # type: ignore[attr-defined]
            vector = _filter_vector_candidate(candidate)
            if vector:
                return vector
        return None
    if isinstance(raw, (list, tuple)):
        if not raw:
            return None
        if all(isinstance(item, (float, int)) for item in raw):
            return [float(item) for item in raw]
        first = raw[0]
        return _filter_vector_candidate(first)
    return None

def _extract_embedding_vector(data: dict) -> list[float] | None:
    for key in ("embedding", "vector"):
        candidate = data.get(key)
        vector = _filter_vector_candidate(candidate)
        if vector:
            return vector
    embeddings = data.get("embeddings")
    vector = _filter_vector_candidate(embeddings)
    if vector:
        return vector
    return _filter_vector_candidate(data.get("data"))

def request_embedding_vector(text: str) -> list[float]:
    payloads = (
        ("/api/embed", {"model": settings.embedding_model, "text": text}),
        ("/api/embeddings", {"model": settings.embedding_model, "prompt": text}),
    )
    data = _call_ollama_endpoint(payloads, settings.ollama_timeout)
    embedding = _extract_embedding_vector(data)
    if not embedding:
        raise RuntimeError("Ollama response missing embedding vector.")
    return embedding

def _extract_generated_text(data: dict) -> str:
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

def generate_response(
    prompt: str,
    model: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    model_name = model or settings.ollama_model
    temp = temperature if temperature is not None else settings.ollama_temperature
    top_k = top_p if top_p is not None else settings.ollama_top_p
    payloads = (
        (
            "/api/generate",
            {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "temperature": temp,
                "top_p": top_k,
            },
        ),
        (
            "/api/chat",
            {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp,
                "top_p": top_k,
            },
        ),
    )
    data = _call_ollama_endpoint(payloads, settings.ollama_generate_timeout)
    text = _extract_generated_text(data)
    if not text:
        raise RuntimeError("Ollama response missing generated text.")
    return text
