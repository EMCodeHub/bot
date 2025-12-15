import sys
from pathlib import Path

from textwrap import dedent

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.app.config import settings
from backend.app.db.postgres import get_connection


def _assert_vector_extension(cur):
    cur.execute("SELECT count(*) AS total FROM pg_extension WHERE extname = 'vector'")
    if cur.fetchone()["total"] != 1:
        raise SystemExit("The vector extension is not installed in the database.")


def _assert_embedding_column(cur):
    cur.execute(
        """
        SELECT format_type(att.atttypid, att.atttypmod) AS type_desc
        FROM pg_attribute AS att
        JOIN pg_class cls ON cls.oid = att.attrelid
        WHERE cls.relname = 'documents' AND att.attname = 'embedding'
        """
    )
    row = cur.fetchone()
    expected = f"vector({settings.embedding_dimension})"
    if not row or row["type_desc"] != expected:
        raise SystemExit(
            dedent(
                f"""\
                Embedding column is {row['type_desc'] if row else 'missing'} but expected {expected}.
                """
            )
        )


def _assert_embedding_dim_check(cur):
    cur.execute(
        """
        SELECT conname, pg_get_constraintdef(oid, true) AS definition
        FROM pg_constraint
        WHERE conrelid = 'documents'::regclass
        AND contype = 'c'
        """
    )
    dim_clause = f"embedding_dim = {settings.embedding_dimension}"
    if not any(dim_clause in row["definition"] for row in cur.fetchall()):
        raise SystemExit("Missing check constraint for embedding_dim.")


def _assert_vector_index(cur):
    cur.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'documents'
          AND indexdef LIKE '%ivfflat%'
        """
    )
    if not cur.fetchone():
        raise SystemExit("The ivfflat vector index is missing.")


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            _assert_vector_extension(cur)
            _assert_embedding_column(cur)
            _assert_embedding_dim_check(cur)
            _assert_vector_index(cur)
    print("Schema verification completed successfully.")


if __name__ == "__main__":
    main()
