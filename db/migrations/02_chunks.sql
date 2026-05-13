-- Requires pgvector extension; skip this file if using Qdrant only.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id  UUID        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_index INT         NOT NULL,
    text        TEXT        NOT NULL,
    embedding   vector(384),          -- adjust dimension to match your embedding model
    coarse_tags TEXT[],
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (article_id, chunk_index)
);

CREATE INDEX idx_chunks_article_id ON chunks(article_id);
-- HNSW index for approximate nearest-neighbour search (cosine distance)
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);