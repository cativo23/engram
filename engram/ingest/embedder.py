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

        _model = TextEmbedding(model_name=settings.embedding_model, cache_dir=settings.fastembed_cache_path)
    return _model


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    """Embed documents/chunks. jina-code needs no special prefix."""
    if not texts:
        return []
    return list(_get_model().embed(texts))


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string."""
    return next(iter(_get_model().embed([text])))
