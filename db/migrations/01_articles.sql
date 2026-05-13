CREATE TABLE articles (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name         TEXT        NOT NULL,
    title               TEXT        NOT NULL,
    url                 TEXT        NOT NULL,
    published_at        TIMESTAMPTZ,
    author              TEXT,
    summary             TEXT,
    full_text           TEXT        NOT NULL,
    content_fingerprint CHAR(64)    NOT NULL,
    extraction_method   TEXT,
    snippet_only        BOOLEAN     NOT NULL DEFAULT FALSE,
    fetched_at          TIMESTAMPTZ,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Deduplication constraints
CREATE UNIQUE INDEX uq_articles_url         ON articles(url);
CREATE UNIQUE INDEX uq_articles_fingerprint ON articles(content_fingerprint);

-- Query support
CREATE INDEX idx_articles_source_name  ON articles(source_name);
CREATE INDEX idx_articles_published_at ON articles(published_at DESC NULLS LAST);
CREATE INDEX idx_articles_ingested_at  ON articles(ingested_at DESC);

-- Full-text search (phase 3 BM25 proxy)
CREATE INDEX idx_articles_fts ON articles
    USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(full_text, '')));