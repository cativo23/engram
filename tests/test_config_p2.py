from engram.config import settings


def test_p2_config_defaults_present():
    assert settings.embedding_model == "jinaai/jina-embeddings-v2-base-code"
    assert settings.embed_dim == 768
    assert settings.chunk_lines == 40
    assert settings.chunk_overlap == 10
    assert settings.search_top_k == 6
    assert settings.database_url.startswith("postgresql://")
    assert settings.repos_dir  # non-empty path
