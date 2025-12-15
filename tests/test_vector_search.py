from datetime import datetime, timezone

from app.config import settings
from app.db import vector_store


def _example_row(distance: float):
    return {
        "text": f"text_{distance}",
        "source": "kb/test",
        "chunk_index": 0,
        "chunk_id": "chunk-id",
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dimension,
        "embedding_version": settings.embedding_version,
        "embedding_norm": 1.0,
        "created_at": datetime.now(tz=timezone.utc),
        "cosine_distance": distance,
    }


def test_search_similar_orders_by_distance(monkeypatch):
    sample_rows = [
        _example_row(0.01),
        _example_row(0.5),
        _example_row(0.9),
    ]

    def fake_query(normalized, top_k):
        return sample_rows[:top_k]

    monkeypatch.setattr(vector_store, "_query_similar_documents", fake_query)

    query = [1.0] * settings.embedding_dimension
    results = vector_store.search_similar(query, top_k=2)

    assert results[0]["text"] == "text_0.01"
    assert results[0]["similarity"] >= results[1]["similarity"]
