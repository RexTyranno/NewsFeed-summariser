CREATE TABLE tone_framing (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id        UUID        NOT NULL UNIQUE REFERENCES articles(id) ON DELETE CASCADE,
    overall_tone      TEXT        CHECK (overall_tone IN ('positive', 'negative', 'neutral')),
    tone_score        FLOAT       CHECK (tone_score BETWEEN -1 AND 1),
    framing_cues      JSONB,      -- e.g. {"hedging": true, "certainty": false, "attribution": true}
    extraction_method TEXT        NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tone_framing_article_id ON tone_framing(article_id);