import math
from unittest.mock import patch

from app.config import settings
from app.llm.embeddings import _cached_embedding, embed_query


class _DummyResponse:
    def __init__(self, vector):
        self._vector = vector

    def raise_for_status(self):
        return None

    def json(self):
        return {"embedding": self._vector}


def _make_embedding():
    base = float(settings.embedding_dimension)
    return [float(i + 1) / base for i in range(settings.embedding_dimension)]


@patch("app.llm.embeddings.requests.post")
def test_embed_query_returns_normalized_vector(mock_post):
    mock_post.return_value = _DummyResponse(_make_embedding())
    _cached_embedding.cache_clear()
    vector = embed_query("hola mundo")
    assert len(vector) == settings.embedding_dimension
    assert all(math.isfinite(value) for value in vector)


@patch("app.llm.embeddings.requests.post")
def test_embed_query_is_deterministic(mock_post):
    mock_post.return_value = _DummyResponse(_make_embedding())
    _cached_embedding.cache_clear()
    result_one = embed_query("   hola   ")
    result_two = embed_query("hola")
    assert result_one == result_two
    assert mock_post.call_count == 1
