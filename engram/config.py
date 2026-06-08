"""Application configuration, loaded from environment variables / .env.

Using pydantic-settings means config is validated and typed: a missing
OPENROUTER_API_KEY fails loudly at startup instead of mid-request.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Field names map to env vars case-insensitively:
    #   openrouter_api_key <- OPENROUTER_API_KEY, model <- MODEL, etc.
    openrouter_api_key: str
    model: str = "openai/gpt-oss-120b:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    max_tool_iterations: int = 5          # safety cap on the agent loop

    # P2 — ingestion + vector store
    database_url: str = "postgresql://engram:engram@db:5432/engram"
    embedding_model: str = "jinaai/jina-embeddings-v2-base-code"
    embed_dim: int = 768
    chunk_lines: int = 40
    chunk_overlap: int = 10
    search_top_k: int = 6
    repos_dir: str = "repos"          # gitignored clone target


settings = Settings()
