import numpy as np

import engram.tools as tools
from tests.conftest import requires_db


class _ctx:
    """Wrap an already-open connection so `with _search_connect() as conn` works."""
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self.conn
    def __exit__(self, *a): return False


@requires_db
def test_search_code_returns_nearest_chunk_as_hit(db_conn, monkeypatch):
    repo_id = db_conn.execute(
        "INSERT INTO repos (slug, indexed_sha) VALUES (%s,%s) RETURNING id",
        ("cativo23/nightwire", "deadbee"),
    ).fetchone()[0]

    def vec(seed):
        v = np.zeros(768, dtype=np.float32)
        v[seed] = 1.0
        return v

    with db_conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (repo_id, path, line_start, line_end, content, content_hash, embedding)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [(repo_id, "modes.css", 40, 46, "[data-mode=archive]{--nw-neon:.6}", "h", vec(0)),
             (repo_id, "other.css", 1, 3, "body{}", "h", vec(5))],
        )
    db_conn.commit()

    monkeypatch.setattr(tools, "embed_query", lambda q: vec(0))
    monkeypatch.setattr(tools, "_search_connect", lambda: _ctx(db_conn))

    hits = tools.search_code("how do intensity modes scale neon?")
    assert hits, "expected at least one hit"
    top = hits[0]
    assert top["repo"] == "cativo23/nightwire"
    assert top["path"] == "modes.css"
    assert top["line_start"] == 40 and top["line_end"] == 46
    assert 0.0 <= top["similarity"] <= 1.0
    assert top["github_url"] == \
        "https://github.com/cativo23/nightwire/blob/deadbee/modes.css#L40-L46"
    assert "neon" in top["snippet"]
