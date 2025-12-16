import os
import sys
import uuid
from pathlib import Path
from typing import Generator, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.app.config import settings
from backend.app.db.postgres import get_connection
from backend.app.llm.ollama_client import request_embedding_vector
from backend.app.utils.text import normalize_text
from backend.app.utils.vector import normalize_embedding

DB = get_connection()
CUR = DB.cursor()

BASE_DIR = ROOT_DIR / "knowledge_base"

if not BASE_DIR.exists():
    raise FileNotFoundError(
        f"No se encontro el directorio {BASE_DIR}. Coloca `knowledge_base` dentro de src/."
    )

ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")
SHORT_FORM_CHUNK_SIZE = 200


def _ensure_extensions() -> None:
    """Make sure the vector extension is available (vector type for pgvector)."""
    CUR.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def _documents_table_exists() -> bool:
    CUR.execute("SELECT to_regclass('public.documents') AS reg")
    result = CUR.fetchone()
    return bool(result and result[0])


def _get_existing_embedding_dimension() -> Optional[int]:
    CUR.execute(
        """
        SELECT a.atttypmod - 4 AS dim
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        WHERE c.relname = 'documents'
        AND a.attname = 'embedding';
        """
    )
    result = CUR.fetchone()
    if not result:
        return None
    return result[0]


def _ensure_documents_table() -> None:
    """Create the documents table so ingestion can insert embeddings."""
    vector_type = f"VECTOR({settings.embedding_dimension})"
    if _documents_table_exists():
        current_dim = _get_existing_embedding_dimension()
        if current_dim and current_dim != settings.embedding_dimension:
            print(
                "Embedding dimension changed "
                f"(was {current_dim}, now {settings.embedding_dimension}); "
                "rebuilding documents table."
            )
            CUR.execute("DROP TABLE documents CASCADE;")
            DB.commit()
    sql = f"""
    CREATE TABLE IF NOT EXISTS documents (
        id SERIAL PRIMARY KEY,
        filepath TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        chunk_id TEXT NOT NULL,
        text TEXT NOT NULL,
        normalized_text TEXT NOT NULL,
        source TEXT NOT NULL,
        embedding {vector_type} NOT NULL,
        embedding_norm DOUBLE PRECISION NOT NULL,
        embedding_model TEXT NOT NULL,
        embedding_dim INTEGER NOT NULL CHECK (embedding_dim = {settings.embedding_dimension}),
        embedding_version TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (filepath, chunk_id)
    );

    CREATE INDEX IF NOT EXISTS documents_chunk_index_idx ON documents (chunk_index);
    CREATE INDEX IF NOT EXISTS documents_embedding_model_idx ON documents (embedding_model);
    CREATE INDEX IF NOT EXISTS documents_embedding_dim_idx ON documents (embedding_dim);
    CREATE INDEX IF NOT EXISTS documents_embedding_vector_idx
        ON documents USING ivfflat (embedding vector_cosine_ops);
    """

    CUR.execute(sql)
    DB.commit()
    print("Ensured documents table exists.")


def _normalize_chunk_starter(text: str) -> str:
    """Normalize markdown text before chunking."""
    normalized = normalize_text(text.replace("\n", " "))
    if not normalized:
        return ""
    return normalized


def chunk_text(text: str, size: int, overlap: int) -> Generator[str, None, None]:
    """Split text into overlapping chunks."""
    words = text.split()
    if size <= 0:
        raise ValueError("Chunk size must be positive.")
    if overlap < 0:
        raise ValueError("Chunk overlap cannot be negative.")
    step = size - overlap
    if step <= 0:
        step = size
    for start in range(0, max(len(words), 1), step):
        chunk_words = words[start : start + size]
        if not chunk_words:
            continue
        yield " ".join(chunk_words)


def embed(text: str) -> tuple[list[float], float]:
    """Request an embedding from Ollama and normalize it."""
    normalized = normalize_text(text)
    try:
        embedding = request_embedding_vector(normalized)
    except RuntimeError as exc:
        raise RuntimeError(f"Error requesting embedding: {exc}") from exc

    return normalize_embedding(embedding, settings.embedding_dimension)


def read_markdown(path: str) -> str:
    """Try common encodings before giving up."""
    for encoding in ENCODINGS:
        try:
            return Path(path).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path} using {ENCODINGS}")


def _is_short_form_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lower()
    basename = os.path.basename(normalized)
    if "/faq/" in normalized or normalized.startswith("faq/"):
        return True
    if basename.startswith("faq_") and basename.endswith(".md"):
        return True
    if basename.endswith("_summary.md"):
        return True
    if basename == "routing.md":
        return True
    return False


def ingest_file(path: str) -> None:
    """Ingest a single Markdown document."""
    relative_path = os.path.relpath(path, BASE_DIR)
    CUR.execute("DELETE FROM documents WHERE filepath = %s", (relative_path,))
    DB.commit()

    raw = read_markdown(path)
    cleaned = _normalize_chunk_starter(raw)
    if not cleaned:
        print(f"Skipping empty document {relative_path}")
        return

    source = relative_path.replace("\\", "/")
    chunk_size = settings.embedding_chunk_size
    if _is_short_form_path(relative_path):
        chunk_size = SHORT_FORM_CHUNK_SIZE
    overlap = settings.embedding_chunk_overlap

    for chunk_index, chunk in enumerate(chunk_text(cleaned, chunk_size, overlap)):
        normalized_chunk = normalize_text(chunk)
        if not normalized_chunk:
            continue

        embedding, embed_norm = embed(normalized_chunk)
        CUR.execute(
            """
            INSERT INTO documents (
                filepath,
                chunk_index,
                chunk_id,
                text,
                normalized_text,
                source,
                embedding,
                embedding_norm,
                embedding_model,
                embedding_dim,
                embedding_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                relative_path,
                chunk_index,
                str(uuid.uuid4()),
                chunk,
                normalized_chunk,
                source,
                embedding,
                embed_norm,
                settings.embedding_model,
                settings.embedding_dimension,
                settings.embedding_version,
            ),
        )

    DB.commit()


def ingest_all() -> None:
    """Walk through the knowledge base and ingest Markdown sources."""
    for root, _, files in os.walk(BASE_DIR):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            full_path = os.path.join(root, filename)
            print("Ingesting:", full_path)
            ingest_file(full_path)


if __name__ == "__main__":
    _ensure_extensions()
    _ensure_documents_table()
    ingest_all()
