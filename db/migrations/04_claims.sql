CREATE TABLE entities (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id   UUID        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    text         TEXT        NOT NULL,
    label        TEXT        NOT NULL,   -- spaCy NER label e.g. ORG, PERSON, GPE
    offset_start INT,
    offset_end   INT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_entities_article_id ON entities(article_id);
CREATE INDEX idx_entities_label      ON entities(label);

CREATE TABLE claims (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id         UUID        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    subject_entity_id  UUID        REFERENCES entities(id) ON DELETE SET NULL,
    predicate          TEXT        NOT NULL,
    object             TEXT        NOT NULL,
    is_numeric         BOOLEAN     NOT NULL DEFAULT FALSE,
    raw_value          TEXT,
    normalized_value   FLOAT,
    unit               TEXT,
    time_phrase        TEXT,
    resolved_date      TIMESTAMPTZ,
    extraction_method  TEXT        NOT NULL,
    confidence         FLOAT       CHECK (confidence BETWEEN 0 AND 1),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_claims_article_id ON claims(article_id);
CREATE INDEX idx_claims_is_numeric ON claims(is_numeric) WHERE is_numeric = TRUE;
CREATE INDEX idx_claims_predicate  ON claims(predicate);