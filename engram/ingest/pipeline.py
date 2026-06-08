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
from .filters import MAX_BYTES, should_index


@dataclass
class IngestResult:
    slug: str
    sha: str
    chunks_inserted: int
    files_indexed: int
    files_skipped_unchanged: int


def _clone_or_pull(slug: str) -> Path:
    """Clone https://github.com/<slug> into repos_dir/<name>, or pull if present."""
    if "/" not in slug or ".." in slug or slug.startswith("/"):
        raise ValueError(f"unsafe repo slug: {slug!r}")
    name = slug.split("/")[-1]
    dest = Path(settings.repos_dir) / name
    if dest.exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only", "-q"], check=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "-c", "core.symlinks=false", "-q",
             f"https://github.com/{slug}.git", str(dest)],
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
    repo_root = repo_path.resolve()
    for p in sorted(repo_path.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue  # never follow symlinks — a repo could symlink to /etc/passwd or ~/.ssh
        try:
            if not p.resolve().is_relative_to(repo_root):
                continue  # defense in depth: resolved path escaped the clone dir
            size = p.stat().st_size
        except OSError:
            continue
        if size > MAX_BYTES:
            continue  # reject oversized BEFORE reading it into memory (bounds peak memory)
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
        chunks = chunk_text(text, settings.chunk_lines, settings.chunk_overlap)
        if not chunks:
            # File is empty/whitespace. Clear stale chunks if it had any; otherwise
            # do nothing — avoids re-deleting a never-chunked file on every run (no churn).
            if existing:
                conn.execute("DELETE FROM chunks WHERE repo_id=%s AND path=%s", (repo_id, rel))
            continue
        vectors = embed_passages([c.text for c in chunks])
        assert len(vectors) == len(chunks), "embedder must return one vector per chunk"
        conn.execute("DELETE FROM chunks WHERE repo_id=%s AND path=%s", (repo_id, rel))
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
