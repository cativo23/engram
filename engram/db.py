"""Postgres + pgvector access.

`connect()` opens a psycopg 3 connection with the pgvector type registered so
numpy arrays round-trip as `vector` values. `init_schema()` creates the tables
and indexes idempotently (safe to call at startup and in tests).
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from .config import settings

_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS repos (
    id          bigserial PRIMARY KEY,
    slug        text UNIQUE NOT NULL,
    indexed_sha text,
    indexed_at  timestamptz
);

CREATE TABLE IF NOT EXISTS chunks (
    id           bigserial PRIMARY KEY,
    repo_id      bigint NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    path         text NOT NULL,
    line_start   int NOT NULL,
    line_end     int NOT NULL,
    content      text NOT NULL,
    content_hash text NOT NULL,
    embedding    vector({dim}) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_repo_path ON chunks (repo_id, path);
"""


@contextmanager
def connect(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Open a connection with the pgvector type registered."""
    conn = psycopg.connect(url or settings.database_url)
    try:
        register_vector(conn)
        yield conn
    finally:
        conn.close()


def init_schema(conn: psycopg.Connection) -> None:
    """Create tables + indexes idempotently. Embedding dim comes from config."""
    conn.execute(_SCHEMA.format(dim=settings.embed_dim))
    conn.commit()
