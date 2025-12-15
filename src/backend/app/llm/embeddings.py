import requests
from functools import lru_cache

from app.config import settings
from app.utils.text import normalize_text
from app.utils.vector import normalize_embedding


@lru_cache(maxsize=256)
def _cached_embedding(text: str):
    """Cache normalized queries so repeated prompts reuse the same vector."""
    try:
        response = requests.post(
            f"{settings.ollama_url}/api/embeddings",
            json={"model": settings.embedding_model, "prompt": text},
            timeout=settings.ollama_timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch embedding: {exc}") from exc

    embedding = response.json().get("embedding")
    if not embedding:
        raise RuntimeError("Ollama response missing embedding vector.")

    normalized, _ = normalize_embedding(embedding, settings.embedding_dimension)
    return tuple(normalized)


def embed_query(text: str):
    """Return a normalized embedding vector using the configured model."""
    normalized_text = normalize_text(text)
    if not normalized_text:
        raise ValueError("Input text must contain readable characters.")
    return list(_cached_embedding(normalized_text))
