from functools import lru_cache

from app.config import settings
from app.llm.ollama_client import request_embedding_vector
from app.utils.text import normalize_text
from app.utils.vector import normalize_embedding


@lru_cache(maxsize=256)
def _cached_embedding(text: str):
    """Cache normalized queries so repeated prompts reuse the same vector."""
    embedding = request_embedding_vector(text)
    normalized, _ = normalize_embedding(embedding, settings.embedding_dimension)
    return tuple(normalized)


def embed_query(text: str):
    """Return a normalized embedding vector using the configured model."""
    normalized_text = normalize_text(text)
    if not normalized_text:
        raise ValueError("Input text must contain readable characters.")
    return list(_cached_embedding(normalized_text))
