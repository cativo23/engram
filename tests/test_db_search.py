import numpy as np

from engram.config import settings
from tests.conftest import requires_db


@requires_db
def test_schema_init_is_idempotent(db_conn):
    from engram.db import init_schema

    init_schema(db_conn)  # second call must not raise
    init_schema(db_conn)
    tables = db_conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
    ).fetchall()
    names = {t[0] for t in tables}
    assert {"repos", "chunks"} <= names


@requires_db
def test_cosine_ordering_returns_nearest_first(db_conn):
    repo_id = db_conn.execute(
        "INSERT INTO repos (slug, indexed_sha) VALUES (%s, %s) RETURNING id",
        ("owner/demo", "abc123"),
    ).fetchone()[0]

    def vec(seed):
        v = np.zeros(settings.embed_dim, dtype=np.float32)
        v[seed] = 1.0
        return v

    rows = [(repo_id, "a.py", 1, 5, "alpha", "h1", vec(0)),
            (repo_id, "b.py", 1, 5, "beta", "h2", vec(1)),
            (repo_id, "c.py", 1, 5, "gamma", "h3", vec(2))]
    with db_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (repo_id, path, line_start, line_end, content, content_hash, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    db_conn.commit()

    query = vec(0)
    nearest = db_conn.execute(
        "SELECT path, 1 - (embedding <=> %s) AS sim FROM chunks ORDER BY embedding <=> %s LIMIT 2",
        (query, query),
    ).fetchall()
    assert nearest[0][0] == "a.py"
    assert nearest[0][1] > nearest[1][1]
