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


def test_embed_passages_empty_returns_empty_without_loading_model(monkeypatch):
    # Must not construct the model (no 640MB download) for an empty batch.
    import engram.ingest.embedder as e
    # Reset module-level singleton so this test is isolated from earlier tests
    # that may have already constructed the model (e.g. slow tests or agent tests).
    monkeypatch.setattr(e, "_model", None)
    assert e._model is None
    assert e.embed_passages([]) == []
    assert e._model is None  # still not loaded
