# Engram P2 — Ingestion + pgvector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Location:** kept OFF-repo under `~/engram-planning/plans/` (like the roadmap). When P2 execution starts on a branch, copy it into `docs/superpowers/plans/` if you want it tracked.

**Goal:** Replace the stubbed `search_code` with real local vector search — clone the configured repos, chunk + embed their files, store them in pgvector, and answer queries with grounded citations to the real files/lines.

**Architecture:** A config/CLI-driven ingestion engine (`engram/ingest/`) clones repos, walks + filters files, splits them into line-window chunks, embeds each chunk locally with fastembed (`jina-embeddings-v2-base-code`, 768-dim), and upserts them into Postgres+pgvector with a per-file content-hash gate for idempotent re-indexing. `search_code` then embeds the query and returns the cosine-nearest chunks in the **exact same hit shape the stub already returns** (so the SSE layer and frontend are unchanged). Runtime repo *selection* is deferred to P2.5 (Admin UI).

**Tech Stack:** Python 3.14, FastAPI (existing), Postgres 16 + pgvector (`pgvector/pgvector:pg16`, already in compose), `psycopg` 3, `pgvector` (Python), `fastembed`, `numpy`, `pytest`. Git CLI for cloning.

**Locked decisions (from roadmap):**
- Admin/repo-selection → **P2.5, separate** (this plan is config/CLI-driven).
- Chunking → **line windows** (40 lines, 10 overlap).
- Embeddings → **`jinaai/jina-embeddings-v2-base-code`, 768-dim** (`vector(768)`; 8192-token ctx; no query/passage prefixes; 640 MB cached in a Docker volume).

**Hit contract (UNCHANGED — the whole point):** `search_code` returns `list[dict]`, each:
`{"repo": "owner/name", "path": "...", "line_start": int, "line_end": int, "similarity": float, "snippet": str, "github_url": "https://github.com/owner/name/blob/<sha>/path#Lstart-Lend"}`.

**Test DB:** the dockerized db is reachable from the host at `postgresql://engram:engram@localhost:5433/engram` (compose maps host 5433 → container 5432). DB-touching tests are gated on env var `ENGRAM_TEST_DATABASE_URL` and skipped when unset, so the pure-unit suite stays fast and offline.

---

## File Structure

**New:**
- `engram/db.py` — connection helper (`connect()` context manager that registers the vector type) + `init_schema(conn)` running idempotent DDL (extension, `repos`, `chunks`, indexes).
- `engram/ingest/__init__.py` — empty package marker.
- `engram/ingest/filters.py` — pure `should_index(path, size_bytes, sample_bytes) -> bool`.
- `engram/ingest/chunker.py` — pure `chunk_text(content, lines_per_chunk, overlap) -> list[Chunk]` (dataclass with line_start/line_end/text).
- `engram/ingest/embedder.py` — lazy fastembed singleton: `embed_passages(list[str]) -> list[np.ndarray]`, `embed_query(str) -> np.ndarray`, `EMBED_DIM = 768`.
- `engram/ingest/pipeline.py` — `ingest_repo(slug, conn) -> IngestResult`: clone/pull → walk → filter → hash-gate → chunk → embed → upsert; updates `repos.indexed_sha`.
- `engram/ingest/__main__.py` — CLI: `python -m engram.ingest owner/name [owner/name ...]`.

**Modified:**
- `requirements.txt` — add `psycopg[binary]`, `pgvector`, `fastembed`, `numpy`.
- `engram/config.py` — add `database_url`, `embedding_model`, `embed_dim`, `chunk_lines`, `chunk_overlap`, `search_top_k`, `repos_dir`.
- `engram/tools.py` — `search_code` body becomes a real pgvector query (signature + return shape unchanged).
- `docker-compose.yml` — add a fastembed model-cache volume on `app`; pass `FASTEMBED_CACHE_PATH`.
- `README.md` — document ingestion (`python -m engram.ingest`) + the compose DB.

**New tests:**
- `tests/test_filters.py`, `tests/test_chunker.py` — pure unit.
- `tests/test_db_search.py` — DB integration (gated), hand-made vectors, no model.
- `tests/test_embedder_smoke.py` — slow/gated model load + shape check.
- `tests/test_pipeline.py` — integration (gated): ingest a tiny fixture repo, assert chunks land + re-index is a no-op.
- `tests/conftest.py` — DB fixtures + skip markers.

---

## Task 1: Dependencies + config

**Files:**
- Modify: `requirements.txt`
- Modify: `engram/config.py`
- Test: `tests/test_config_p2.py`

- [ ] **Step 1: Add the runtime dependencies**

Replace the P2 comment block in `requirements.txt` with real pins (append after the existing pinned deps):

```text
# P2 — ingestion + vector store
psycopg[binary]==3.2.3
pgvector==0.3.6
fastembed==0.4.2
numpy==2.2.1
```

- [ ] **Step 2: Install them**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: `Successfully installed fastembed-... numpy-... pgvector-... psycopg-...`

- [ ] **Step 3: Write the failing config test**

Create `tests/test_config_p2.py`:

```python
from engram.config import settings


def test_p2_config_defaults_present():
    assert settings.embedding_model == "jinaai/jina-embeddings-v2-base-code"
    assert settings.embed_dim == 768
    assert settings.chunk_lines == 40
    assert settings.chunk_overlap == 10
    assert settings.search_top_k == 6
    # database_url has a sensible in-container default
    assert settings.database_url.startswith("postgresql://")
    assert settings.repos_dir  # non-empty path
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config_p2.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'embedding_model'`.

- [ ] **Step 5: Add the fields to `engram/config.py`**

In `engram/config.py`, add these fields to the `Settings` class (after `max_tool_iterations`):

```python
    # P2 — ingestion + vector store
    database_url: str = "postgresql://engram:engram@db:5432/engram"
    embedding_model: str = "jinaai/jina-embeddings-v2-base-code"
    embed_dim: int = 768
    chunk_lines: int = 40
    chunk_overlap: int = 10
    search_top_k: int = 6
    repos_dir: str = "repos"          # gitignored clone target
```

- [ ] **Step 6: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config_p2.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt engram/config.py tests/test_config_p2.py
git commit -m "feat(p2): add ingestion/vector config and dependencies"
```

---

## Task 2: DB layer + schema

**Files:**
- Create: `engram/db.py`
- Create: `tests/conftest.py`
- Create: `tests/test_db_search.py`

- [ ] **Step 1: Create the DB fixtures (`tests/conftest.py`)**

```python
import os

import pytest


def _test_db_url():
    return os.environ.get("ENGRAM_TEST_DATABASE_URL")


requires_db = pytest.mark.skipif(
    _test_db_url() is None,
    reason="set ENGRAM_TEST_DATABASE_URL (e.g. postgresql://engram:engram@localhost:5433/engram) to run DB tests",
)


@pytest.fixture
def db_conn():
    """A connection to the test DB with a fresh schema, rolled back after the test."""
    from engram.db import connect, init_schema

    url = _test_db_url()
    with connect(url) as conn:
        init_schema(conn)
        # Clean slate for each test.
        conn.execute("TRUNCATE chunks, repos RESTART IDENTITY CASCADE")
        conn.commit()
        yield conn
```

- [ ] **Step 2: Write the failing DB test**

Create `tests/test_db_search.py`:

```python
import numpy as np

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
    # Insert a repo and three chunks with hand-made 768-dim vectors (no model).
    repo_id = db_conn.execute(
        "INSERT INTO repos (slug, indexed_sha) VALUES (%s, %s) RETURNING id",
        ("owner/demo", "abc123"),
    ).fetchone()[0]

    def vec(seed):
        v = np.zeros(768, dtype=np.float32)
        v[seed] = 1.0
        return v

    rows = [(repo_id, "a.py", 1, 5, "alpha", "h1", vec(0)),
            (repo_id, "b.py", 1, 5, "beta", "h2", vec(1)),
            (repo_id, "c.py", 1, 5, "gamma", "h3", vec(2))]
    db_conn.cursor().executemany(
        "INSERT INTO chunks (repo_id, path, line_start, line_end, content, content_hash, embedding)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        rows,
    )
    db_conn.commit()

    query = vec(0)  # identical to a.py's vector -> a.py is nearest
    nearest = db_conn.execute(
        "SELECT path, 1 - (embedding <=> %s) AS sim FROM chunks ORDER BY embedding <=> %s LIMIT 2",
        (query, query),
    ).fetchall()
    assert nearest[0][0] == "a.py"
    assert nearest[0][1] > nearest[1][1]  # higher cosine similarity first
```

- [ ] **Step 3: Run it to verify it fails**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_db_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engram.db'` (the docker db must be up: `docker compose up -d db`).

- [ ] **Step 4: Create `engram/db.py`**

```python
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
```

- [ ] **Step 5: Run it to verify it passes**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_db_search.py -v`
Expected: PASS (2 passed). Without the env var the tests are skipped.

- [ ] **Step 6: Commit**

```bash
git add engram/db.py tests/conftest.py tests/test_db_search.py
git commit -m "feat(p2): pgvector db layer with idempotent schema"
```

---

## Task 3: File filter

**Files:**
- Create: `engram/ingest/__init__.py` (empty)
- Create: `engram/ingest/filters.py`
- Test: `tests/test_filters.py`

- [ ] **Step 1: Create the package marker**

Create `engram/ingest/__init__.py` (empty file):

```python
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_filters.py`:

```python
from engram.ingest.filters import should_index

MAX = 1_000_000


def test_indexes_normal_source_file():
    assert should_index("engram/agent.py", 2_000, b"def run():\n    pass\n") is True


def test_skips_oversized_file():
    assert should_index("big.py", MAX + 1, b"x = 1\n") is False


def test_skips_binary_with_null_bytes():
    assert should_index("logo.py", 50, b"\x00\x01\x02binary") is False


def test_skips_dotenv_and_secrets():
    assert should_index(".env", 10, b"SECRET=1") is False
    assert should_index("config/.env.local", 10, b"SECRET=1") is False


def test_skips_lockfiles_and_vendored_dirs():
    assert should_index("package-lock.json", 500, b"{}") is False
    assert should_index("node_modules/x/index.js", 50, b"x") is False
    assert should_index(".git/config", 50, b"x") is False


def test_skips_known_binary_extensions():
    assert should_index("img/logo.png", 50, b"\x89PNG") is False
    assert should_index("font.woff2", 50, b"x") is False
```

- [ ] **Step 3: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_filters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engram.ingest.filters'`.

- [ ] **Step 4: Create `engram/ingest/filters.py`**

```python
"""Decide which repo files to index. Conservative: skip anything binary,
oversized, secret-bearing, vendored, or a lockfile."""

import os

MAX_BYTES = 1_000_000  # 1 MB

_SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv",
              "__pycache__", ".next", ".cache", "target"}
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
               "poetry.lock", "composer.lock", "Cargo.lock"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
               ".woff", ".woff2", ".ttf", ".eot", ".zip", ".gz", ".tar",
               ".mp4", ".mov", ".mp3", ".wasm", ".so", ".dylib", ".o", ".pyc"}


def should_index(path: str, size_bytes: int, sample_bytes: bytes) -> bool:
    """`sample_bytes` is the first chunk of the file (for binary detection)."""
    if size_bytes > MAX_BYTES:
        return False
    parts = path.replace("\\", "/").split("/")
    if any(p in _SKIP_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in _SKIP_NAMES:
        return False
    if name == ".env" or name.startswith(".env."):
        return False
    if os.path.splitext(name)[1].lower() in _BINARY_EXT:
        return False
    if b"\x00" in sample_bytes:  # null byte -> binary
        return False
    return True
```

- [ ] **Step 5: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_filters.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add engram/ingest/__init__.py engram/ingest/filters.py tests/test_filters.py
git commit -m "feat(p2): conservative file filter for ingestion"
```

---

## Task 4: Line-window chunker

**Files:**
- Create: `engram/ingest/chunker.py`
- Test: `tests/test_chunker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_chunker.py`:

```python
from engram.ingest.chunker import chunk_text


def _lines(n):
    return "\n".join(f"line{i}" for i in range(1, n + 1))


def test_short_file_is_one_chunk():
    chunks = chunk_text(_lines(10), lines_per_chunk=40, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].line_start == 1
    assert chunks[0].line_end == 10
    assert chunks[0].text.startswith("line1")


def test_windows_with_overlap_cover_all_lines():
    chunks = chunk_text(_lines(100), lines_per_chunk=40, overlap=10)
    # step = 40 - 10 = 30 -> starts at 1, 31, 61, 91
    assert [c.line_start for c in chunks] == [1, 31, 61, 91]
    assert chunks[0].line_end == 40
    assert chunks[-1].line_end == 100  # last window clamps to EOF
    # overlap: chunk 2 starts 10 lines before chunk 1 ends
    assert chunks[1].line_start == chunks[0].line_end - 10 + 1


def test_empty_or_whitespace_file_yields_no_chunks():
    assert chunk_text("", lines_per_chunk=40, overlap=10) == []
    assert chunk_text("   \n  \n", lines_per_chunk=40, overlap=10) == []


def test_line_ranges_are_1_indexed_and_text_matches():
    chunks = chunk_text(_lines(5), lines_per_chunk=2, overlap=0)
    assert [(c.line_start, c.line_end) for c in chunks] == [(1, 2), (3, 4), (5, 5)]
    assert chunks[1].text == "line3\nline4"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chunker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engram.ingest.chunker'`.

- [ ] **Step 3: Create `engram/ingest/chunker.py`**

```python
"""Split file text into overlapping line-window chunks.

Line windows are language-agnostic and fast. The embedding model has an 8192-token
context, so 40-line windows never truncate. Line numbers are 1-indexed (to match
GitHub deep links). P2.5+ may upgrade to code-aware (tree-sitter) chunking.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    line_start: int  # 1-indexed, inclusive
    line_end: int    # 1-indexed, inclusive
    text: str


def chunk_text(content: str, lines_per_chunk: int, overlap: int) -> list[Chunk]:
    """Sliding window over lines. `overlap` lines repeat between adjacent chunks."""
    if not content.strip():
        return []
    lines = content.split("\n")
    n = len(lines)
    step = max(1, lines_per_chunk - overlap)
    chunks: list[Chunk] = []
    start = 0  # 0-indexed line offset
    while start < n:
        end = min(start + lines_per_chunk, n)  # exclusive
        text = "\n".join(lines[start:end])
        chunks.append(Chunk(line_start=start + 1, line_end=end, text=text))
        if end == n:
            break
        start += step
    return chunks
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chunker.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add engram/ingest/chunker.py tests/test_chunker.py
git commit -m "feat(p2): line-window chunker"
```

---

## Task 5: Embedder (fastembed wrapper)

**Files:**
- Create: `engram/ingest/embedder.py`
- Test: `tests/test_embedder_smoke.py`

- [ ] **Step 1: Write the (slow, gated) smoke test**

Create `tests/test_embedder_smoke.py`:

```python
import os

import numpy as np
import pytest

slow = pytest.mark.skipif(
    os.environ.get("ENGRAM_RUN_SLOW") is None,
    reason="set ENGRAM_RUN_SLOW=1 to download the model and run embedder smoke tests",
)


@slow
def test_embeds_to_configured_dimension():
    from engram.config import settings
    from engram.ingest.embedder import embed_passages, embed_query

    vecs = embed_passages(["def run(): pass", "the agent loop"])
    assert len(vecs) == 2
    assert vecs[0].shape == (settings.embed_dim,)
    assert isinstance(vecs[0], np.ndarray)

    q = embed_query("where is the agent loop?")
    assert q.shape == (settings.embed_dim,)
```

- [ ] **Step 2: Run it (skipped by default)**

Run: `.venv/bin/python -m pytest tests/test_embedder_smoke.py -v`
Expected: SKIPPED (1 skipped) — confirms the gate works without downloading the model.

- [ ] **Step 3: Create `engram/ingest/embedder.py`**

```python
"""Local embeddings via fastembed. The model is loaded lazily (first use) and
reused — its first construction downloads ~640 MB, so we never build it at import.
"""

import numpy as np

from ..config import settings

_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    """Embed documents/chunks. jina-code needs no special prefix."""
    if not texts:
        return []
    return list(_get_model().embed(texts))


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string."""
    return next(iter(_get_model().embed([text])))
```

- [ ] **Step 4: Verify (gated)**

Run: `ENGRAM_RUN_SLOW=1 .venv/bin/python -m pytest tests/test_embedder_smoke.py -v`
Expected: PASS (downloads the model on first run; assert vectors are 768-dim). If skipping the download in this environment, at minimum run the default (skipped) command from Step 2 and note the model load is verified during Task 7's integration run.

- [ ] **Step 5: Commit**

```bash
git add engram/ingest/embedder.py tests/test_embedder_smoke.py
git commit -m "feat(p2): lazy fastembed embedder (jina-code, 768d)"
```

---

## Task 6: Ingestion pipeline + CLI

**Files:**
- Create: `engram/ingest/pipeline.py`
- Create: `engram/ingest/__main__.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing integration test (gated)**

Create `tests/test_pipeline.py`:

```python
import subprocess
from pathlib import Path

from tests.conftest import requires_db


def _make_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "main.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / ".env").write_text("SECRET=should-be-skipped\n")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


@requires_db
def test_ingest_local_repo_inserts_chunks_and_skips_secrets(db_conn, tmp_path, monkeypatch):
    from engram.ingest import pipeline

    # Embed deterministically without the model: 768-dim hashed vector.
    import numpy as np

    def fake_embed(texts):
        out = []
        for t in texts:
            v = np.zeros(768, dtype=np.float32)
            v[hash(t) % 768] = 1.0
            out.append(v)
        return out

    monkeypatch.setattr(pipeline, "embed_passages", fake_embed)

    repo_path = _make_fixture_repo(tmp_path)
    result = pipeline.ingest_repo("owner/demo", db_conn, local_path=repo_path)

    assert result.chunks_inserted >= 1
    paths = [r[0] for r in db_conn.execute("SELECT DISTINCT path FROM chunks").fetchall()]
    assert "main.py" in paths
    assert ".env" not in paths  # filter skipped the secret

    # Re-index with no changes -> hash gate skips everything.
    again = pipeline.ingest_repo("owner/demo", db_conn, local_path=repo_path)
    assert again.chunks_inserted == 0
    assert again.files_skipped_unchanged >= 1
```

- [ ] **Step 2: Run it to verify it fails**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'engram.ingest.pipeline'`.

- [ ] **Step 3: Create `engram/ingest/pipeline.py`**

```python
"""Ingest a repo into pgvector: clone/pull -> walk -> filter -> hash-gate ->
chunk -> embed -> upsert. Idempotent: unchanged files (by content hash) are skipped.
"""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import settings
from .chunker import chunk_text
from .embedder import embed_passages
from .filters import should_index


@dataclass
class IngestResult:
    slug: str
    sha: str
    chunks_inserted: int
    files_indexed: int
    files_skipped_unchanged: int


def _clone_or_pull(slug: str) -> Path:
    """Clone https://github.com/<slug> into repos_dir/<name>, or pull if present."""
    name = slug.split("/")[-1]
    dest = Path(settings.repos_dir) / name
    if dest.exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only", "-q"], check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "-q", f"https://github.com/{slug}.git", str(dest)],
            check=True,
        )
    return dest


def _head_sha(repo_path: Path) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def _walk_files(repo_path: Path):
    for p in sorted(repo_path.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_path).as_posix()
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        if not should_index(rel, len(raw), raw[:1024]):
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        yield rel, text


def _upsert_repo(conn, slug: str, sha: str) -> int:
    row = conn.execute(
        """INSERT INTO repos (slug, indexed_sha, indexed_at)
           VALUES (%s, %s, now())
           ON CONFLICT (slug) DO UPDATE SET indexed_sha = EXCLUDED.indexed_sha,
                                            indexed_at = now()
           RETURNING id""",
        (slug, sha),
    ).fetchone()
    return row[0]


def ingest_repo(slug: str, conn, local_path: Path | None = None) -> IngestResult:
    """Index one repo. `local_path` (tests) skips cloning."""
    repo_path = local_path or _clone_or_pull(slug)
    sha = _head_sha(repo_path)
    repo_id = _upsert_repo(conn, slug, sha)

    inserted = indexed = skipped = 0
    for rel, text in _walk_files(repo_path):
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = conn.execute(
            "SELECT content_hash FROM chunks WHERE repo_id=%s AND path=%s LIMIT 1",
            (repo_id, rel),
        ).fetchone()
        if existing and existing[0] == content_hash:
            skipped += 1
            continue
        # File new or changed: replace its chunks.
        conn.execute("DELETE FROM chunks WHERE repo_id=%s AND path=%s", (repo_id, rel))
        chunks = chunk_text(text, settings.chunk_lines, settings.chunk_overlap)
        if not chunks:
            continue
        vectors = embed_passages([c.text for c in chunks])
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO chunks
                   (repo_id, path, line_start, line_end, content, content_hash, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(repo_id, rel, c.line_start, c.line_end, c.text, content_hash, v)
                 for c, v in zip(chunks, vectors)],
            )
        inserted += len(chunks)
        indexed += 1
    conn.commit()
    return IngestResult(slug, sha, inserted, indexed, skipped)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_pipeline.py -v`
Expected: PASS (1 passed) — chunks inserted, `.env` skipped, re-index is a no-op.

- [ ] **Step 5: Create the CLI `engram/ingest/__main__.py`**

```python
"""CLI: python -m engram.ingest owner/name [owner/name ...]"""

import sys

from ..db import connect, init_schema
from .pipeline import ingest_repo


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m engram.ingest owner/name [owner/name ...]", file=sys.stderr)
        return 2
    with connect() as conn:
        init_schema(conn)
        for slug in argv:
            print(f"indexing {slug} ...", flush=True)
            r = ingest_repo(slug, conn)
            print(f"  sha={r.sha[:8]} files={r.files_indexed} "
                  f"chunks+={r.chunks_inserted} unchanged={r.files_skipped_unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 6: Commit**

```bash
git add engram/ingest/pipeline.py engram/ingest/__main__.py tests/test_pipeline.py
git commit -m "feat(p2): ingestion pipeline with content-hash idempotency + CLI"
```

---

## Task 7: Real `search_code`

**Files:**
- Modify: `engram/tools.py`
- Test: `tests/test_search_code_real.py`

- [ ] **Step 1: Write the failing integration test (gated)**

Create `tests/test_search_code_real.py`:

```python
import numpy as np

import engram.tools as tools
from tests.conftest import requires_db


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

    db_conn.cursor().executemany(
        "INSERT INTO chunks (repo_id, path, line_start, line_end, content, content_hash, embedding)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s)",
        [(repo_id, "modes.css", 40, 46, "[data-mode=archive]{--nw-neon:.6}", "h", vec(0)),
         (repo_id, "other.css", 1, 3, "body{}", "h", vec(5))],
    )
    db_conn.commit()

    # search_code embeds the query — stub the embedder to hit the modes.css vector.
    monkeypatch.setattr(tools, "embed_query", lambda q: vec(0))
    # Point search_code at the test connection.
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


class _ctx:
    """Wrap an already-open connection so `with _search_connect() as conn` works."""
    def __init__(self, conn): self.conn = conn
    def __enter__(self): return self.conn
    def __exit__(self, *a): return False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_search_code_real.py -v`
Expected: FAIL — `AttributeError` / `search_code` still returns the stub hits (no `embed_query`/`_search_connect` in `tools`).

- [ ] **Step 3: Replace the stub body in `engram/tools.py`**

Replace the `search_code` stub function (keep `TOOLS_SCHEMA`, `format_hits_for_model`, `run_tool`, `TOOL_FUNCTIONS` unchanged) with the real implementation, and add the two imports + the `_search_connect` indirection (so tests can inject a connection):

At the top of `engram/tools.py`, add:

```python
from .db import connect
from .ingest.embedder import embed_query


def _search_connect():
    """Indirection so tests can inject a live connection."""
    return connect()
```

Then replace the stub `search_code(query)` with:

```python
def search_code(query: str) -> list[dict]:
    """Embed the query and return the cosine-nearest indexed chunks as hits.

    Return shape is identical to the P1 stub, so the agent/SSE/frontend are
    unchanged — only the values are now real.
    """
    from .config import settings

    vector = embed_query(query)
    sql = (
        "SELECT r.slug, r.indexed_sha, c.path, c.line_start, c.line_end, c.content, "
        "       1 - (c.embedding <=> %s) AS similarity "
        "FROM chunks c JOIN repos r ON r.id = c.repo_id "
        "ORDER BY c.embedding <=> %s LIMIT %s"
    )
    with _search_connect() as conn:
        rows = conn.execute(sql, (vector, vector, settings.search_top_k)).fetchall()

    hits = []
    for slug, sha, path, start, end, content, similarity in rows:
        ref = sha or "main"
        hits.append({
            "repo": slug,
            "path": path,
            "line_start": start,
            "line_end": end,
            "similarity": round(float(similarity), 4),
            "snippet": content,
            "github_url": f"https://github.com/{slug}/blob/{ref}/{path}#L{start}-L{end}",
        })
    return hits
```

Remove the old hardcoded stub return.

- [ ] **Step 4: Run it to verify it passes**

Run: `ENGRAM_TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram .venv/bin/python -m pytest tests/test_search_code_real.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `.venv/bin/python -m pytest -q` (DB tests skip without the env var)
Expected: all non-gated tests PASS. Note: `tests/test_tools.py::test_search_code_returns_structured_hits` and `test_run_tool_*` previously asserted on the stub's fixed values — UPDATE those to assert only on the *shape* (keys present, types), since values are now DB-driven. Show the engineer the edit:

In `tests/test_tools.py`, change `test_search_code_returns_structured_hits` and `test_run_tool_dispatches_to_search_code` so they no longer call the real DB-backed `search_code` directly (it now needs a DB + model). Instead, assert the **formatter/dispatch** behavior with hand-built hits, and move the live `search_code` assertion into the gated `tests/test_search_code_real.py` (already done). Concretely, replace those two stub-value tests with:

```python
def test_format_and_dispatch_shape_only():
    # search_code is now DB-backed (covered by the gated integration test);
    # here we only verify the model-facing formatter on a known hit.
    hit = {"repo": "o/r", "path": "a.py", "line_start": 1, "line_end": 9,
           "similarity": 0.9, "snippet": "code", "github_url": "u"}
    text = format_hits_for_model([hit])
    assert "[1] o/r · a.py:1-9" in text and "code" in text
```

(Delete `test_search_code_returns_structured_hits` and `test_run_tool_dispatches_to_search_code`; keep `test_run_tool_unknown_returns_empty`, `test_run_tool_ignores_unexpected_model_arguments`, and the other formatter tests.)

- [ ] **Step 6: Commit**

```bash
git add engram/tools.py tests/test_search_code_real.py tests/test_tools.py
git commit -m "feat(p2): real pgvector search_code (retires the stub)"
```

---

## Task 8: Wire-up, end-to-end ingest, docs

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile`
- Modify: `README.md`

- [ ] **Step 1: Persist the fastembed model cache (avoid re-download on restart)**

In `docker-compose.yml`, add to the `app` service a named volume for the model cache and set the cache path:

```yaml
  app:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql://engram:engram@db:5432/engram
      FASTEMBED_CACHE_PATH: /app/.fastembed_cache
    volumes:
      - engram-fastembed:/app/.fastembed_cache
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
```

And add `engram-fastembed:` under the top-level `volumes:` block (next to `engram-pgdata:`).

- [ ] **Step 2: Initialize the schema on app startup**

In `engram/main.py`, add a startup hook so the tables exist when the app serves (idempotent). Add after `app = FastAPI(...)`:

```python
@app.on_event("startup")
def _ensure_schema() -> None:
    from .db import connect, init_schema
    try:
        with connect() as conn:
            init_schema(conn)
    except Exception:
        logger.exception("schema init skipped (db unavailable)")
```

(Non-fatal: if the DB is down, the app still serves the UI / `/health`.)

- [ ] **Step 3: Rebuild + run the stack, then ingest for real**

```bash
docker compose up -d --build
# Ingest a couple of repos (runs inside the app container so it shares the DB + cache):
docker compose exec app python -m engram.ingest cativo23/nightwire cativo23/engram
```
Expected: log lines like `indexing cativo23/nightwire ... sha=... files=N chunks+=M unchanged=0`. First run downloads the model (~640 MB) into the cache volume.

- [ ] **Step 4: Verify a real grounded answer end-to-end**

```bash
curl -N -s -X POST http://127.0.0.1:8000/chat -H 'Content-Type: application/json' \
  -d '{"message":"how do nightwire intensity modes scale neon?"}'
```
Expected: `citations` frames now cite **real** nightwire files/lines (not the agent-loop stub), and the answer is grounded in them. Open `http://127.0.0.1:8000/` and confirm the matching repo fires for real.

- [ ] **Step 5: Document ingestion in the README**

Add an `## Indexing your repos (P2)` section to `README.md`:

```markdown
## Indexing your repos (P2)

Engram searches repos you index locally — nothing is sent to a third party except
the LLM calls. Bring up the stack, then index one or more public repos:

\`\`\`bash
docker compose up -d
docker compose exec app python -m engram.ingest owner/name [owner/name ...]
\`\`\`

Re-running is idempotent: unchanged files (by content hash) are skipped. Embeddings
are computed locally with fastembed (`jina-embeddings-v2-base-code`, 768-dim) and
stored in Postgres + pgvector. Runtime repo selection via an admin UI is planned (P2.5).
```

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml Dockerfile engram/main.py README.md
git commit -m "feat(p2): startup schema init, model cache volume, ingest docs"
```

---

## Self-Review

**Spec coverage (roadmap P2):**
- DB schema + migrations → Task 2 (`init_schema`, repos/chunks, HNSW + lookup index). ✓
- DB access layer + `DATABASE_URL` config → Task 1 (config) + Task 2 (`connect`). ✓
- Ingestion pipeline (clone/pull → walk → filter → chunk → embed → upsert, hash gate) → Tasks 3–6. ✓
- CLI entrypoint → Task 6 (`python -m engram.ingest`). ✓
- Real `search_code` (same hit shape, pinned sha URL) → Task 7. ✓
- Config-driven (model, chunk params, top-k, repos_dir) → Task 1. ✓
- Tests: chunker, filter, hash gate (re-index skip), URL builder, integration search → Tasks 3,4,6,7. ✓
- fastembed cache as a Docker volume → Task 8. ✓
- Retire the stub → Task 7. ✓
- Don't index secrets (`.env`) → Task 3 (filter) + asserted in Task 6 pipeline test. ✓

**Decisions honored:** line-window chunking (Task 4), jina-code 768-dim (`vector(768)`, Task 2/Task 1), admin deferred to P2.5 (no admin code here). ✓

**Placeholder scan:** every code step has complete code; SQL, psycopg, fastembed, and git calls are concrete; no "TBD"/"add error handling". Gated tests have explicit skip reasons + the exact env var to enable them.

**Type/name consistency:** `Chunk(line_start, line_end, text)` defined in Task 4 and consumed in Task 6. `IngestResult(slug, sha, chunks_inserted, files_indexed, files_skipped_unchanged)` defined + asserted consistently (Task 6 test uses `chunks_inserted`, `files_skipped_unchanged`). `embed_passages`/`embed_query` defined Task 5, used in Tasks 6/7. `connect`/`init_schema` defined Task 2, used in Tasks 6/7/8. Hit dict keys identical to the existing contract (`repo, path, line_start, line_end, similarity, snippet, github_url`) — verified against `format_hits_for_model` (`repo · path:line_start-line_end`) and the frontend reducer/render. `search_top_k`/`embed_dim`/`chunk_lines`/`chunk_overlap` names match between config (Task 1) and consumers.

**Known follow-ups (not P2):** background/async ingestion + progress, `/repos` endpoint + data-driven INDEX CORE, admin UI + auth → all P2.5. Move `CONVERSATIONS` to DB → P4. Pin SOURCE-LOCK href host → backlog.
