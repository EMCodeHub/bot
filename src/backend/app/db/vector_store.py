from typing import Iterable, List, Sequence

from pgvector import Vector

from app.config import settings
from app.db.postgres import get_cursor
from app.utils.vector import normalize_embedding


def _query_similar_documents(
    normalized_embedding: list[float],
    top_k: int,
    source_prefixes: Sequence[str] | None = None,
) -> Iterable[dict]:
    """
    Use pgvector cosine distance operator to rank nearest chunks.
    Optionally restrict search to documents whose source path starts with one
    of the provided prefixes.
    """
    with get_cursor() as (_, cur):
        query = """
            SELECT
                text,
                source,
                chunk_index,
                chunk_id,
                embedding_model,
                embedding_dim,
                embedding_version,
                embedding_norm,
                created_at,
                embedding <#> %s AS cosine_distance
            FROM documents
        """
        params = [Vector(normalized_embedding)]
        conditions: list[str] = []
        if source_prefixes:
            patterns = []
            for prefix in source_prefixes:
                normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
                patterns.append(f"{normalized_prefix}%")
            conditions.append("source ILIKE ANY (%s)")
            params.append(patterns)
        if conditions:
            query += "\nWHERE " + " AND ".join(conditions)
        query += """
            ORDER BY cosine_distance ASC
            LIMIT %s
            """
        params.append(top_k)
        cur.execute(query, tuple(params))
        return cur.fetchall()


def search_similar(
    query_embedding: list[float],
    top_k: int = 3,
    source_prefixes: Sequence[str] | None = None,
):
    normalized_embedding, _ = normalize_embedding(query_embedding, settings.embedding_dimension)
    rows = _query_similar_documents(normalized_embedding, top_k, source_prefixes)
    results = []
    for row in rows:
        distance = row.get("cosine_distance", 1.0)
        similarity = max(0.0, 1.0 - distance)
        results.append(
            {
                "text": row["text"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "chunk_id": row["chunk_id"],
                "embedding_model": row["embedding_model"],
                "embedding_dim": row["embedding_dim"],
                "embedding_version": row["embedding_version"],
                "embedding_norm": row["embedding_norm"],
                "created_at": row["created_at"],
                "similarity": similarity,
            }
        )
    return results


def get_chunks_by_filepaths(filepaths: Sequence[str]) -> List[dict]:
    """Return chunks that match the provided filepaths."""
    if not filepaths:
        return []
    with get_cursor() as (_, cur):
        cur.execute(
            """
            SELECT
                text,
                source,
                chunk_index,
                chunk_id,
                embedding_model,
                embedding_dim,
                embedding_version,
                embedding_norm,
                created_at
            FROM documents
            WHERE filepath = ANY (%s)
            ORDER BY created_at DESC
            """,
            (list(filepaths),),
        )
        rows = cur.fetchall()

    results: List[dict] = []
    for row in rows:
        results.append(
            {
                "text": row["text"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "chunk_id": row["chunk_id"],
                "embedding_model": row["embedding_model"],
                "embedding_dim": row["embedding_dim"],
                "embedding_version": row["embedding_version"],
                "embedding_norm": row["embedding_norm"],
                "created_at": row["created_at"],
                "similarity": 1.0,
            }
        )
    return results


def find_texts_with_keywords(keywords: Iterable[str], max_results: int = 2) -> List[str]:
    """Return documents whose normalized text contains any of the keywords."""
    lowered = [kw.strip().lower() for kw in keywords if kw.strip()]
    if not lowered:
        return []

    patterns = [f"%{word}%" for word in lowered]
    with get_cursor() as (_, cur):
        cur.execute(
            """
            SELECT text
            FROM documents
            WHERE normalized_text ILIKE ANY (%s)
            LIMIT %s
            """,
            (patterns, max_results),
        )
        rows = cur.fetchall()

    seen = set()
    matches = []
    for row in rows:
        text = row["text"]
        if text in seen:
            continue
        seen.add(text)
        matches.append(text)
    return matches
