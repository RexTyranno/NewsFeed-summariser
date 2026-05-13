CREATE TABLE ingestion_jobs (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_url          TEXT        NOT NULL,
    status            TEXT        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'running', 'done', 'failed')),
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    articles_inserted INT         NOT NULL DEFAULT 0,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ingestion_jobs_feed_url ON ingestion_jobs(feed_url);
CREATE INDEX idx_ingestion_jobs_status   ON ingestion_jobs(status);
CREATE INDEX idx_ingestion_jobs_created  ON ingestion_jobs(created_at DESC);