-- Runs once on first DB init (mounted into /docker-entrypoint-initdb.d/).
-- Enables the pgvector extension so P2 can store/query embeddings.
CREATE EXTENSION IF NOT EXISTS vector;
