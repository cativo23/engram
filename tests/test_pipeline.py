import subprocess
from pathlib import Path

import numpy as np

from engram.config import settings
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

    def fake_embed(texts):
        out = []
        for t in texts:
            v = np.zeros(settings.embed_dim, dtype=np.float32)
            v[hash(t) % settings.embed_dim] = 1.0
            out.append(v)
        return out

    monkeypatch.setattr(pipeline, "embed_passages", fake_embed)

    repo_path = _make_fixture_repo(tmp_path)
    result = pipeline.ingest_repo("owner/demo", db_conn, local_path=repo_path)

    assert result.chunks_inserted >= 1
    paths = [r[0] for r in db_conn.execute("SELECT DISTINCT path FROM chunks").fetchall()]
    assert "main.py" in paths
    assert ".env" not in paths  # filter skipped the secret

    again = pipeline.ingest_repo("owner/demo", db_conn, local_path=repo_path)
    assert again.chunks_inserted == 0
    assert again.files_indexed == 0
    assert again.files_skipped_unchanged >= 1


@requires_db
def test_ingest_skips_symlinks(db_conn, tmp_path, monkeypatch):
    from engram.ingest import pipeline

    monkeypatch.setattr(pipeline, "embed_passages",
                        lambda texts: [np.zeros(settings.embed_dim, dtype=np.float32) for _ in texts])

    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET\n")
    repo = tmp_path / "demo2"
    repo.mkdir()
    (repo / "main.py").write_text("x = 1\n")
    (repo / "link.txt").symlink_to(secret)  # symlink pointing OUTSIDE the repo
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=repo, check=True)

    pipeline.ingest_repo("owner/demo2", db_conn, local_path=repo)
    paths = [r[0] for r in db_conn.execute("SELECT DISTINCT path FROM chunks").fetchall()]
    assert "main.py" in paths
    assert "link.txt" not in paths  # symlink was NOT followed/indexed
