CREATE TABLE events (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id       UUID        NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    text             TEXT        NOT NULL,
    offset_start     INT,
    offset_end       INT,
    time_expr_type   TEXT        CHECK (time_expr_type IN
                         ('absolute', 'relative_to_publish', 'relative_to_event', 'vague')),
    resolved_start   TIMESTAMPTZ,
    resolved_end     TIMESTAMPTZ,
    certainty        TEXT        CHECK (certainty IN ('firm', 'inferred', 'tentative')),
    anchor_event_id  UUID        REFERENCES events(id) ON DELETE SET NULL,
    resolution_notes TEXT,
    extraction_method TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_article_id     ON events(article_id);
CREATE INDEX idx_events_resolved_start ON events(resolved_start NULLS LAST);

CREATE TABLE event_links (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_event_id UUID        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    target_event_id UUID        NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    relation        TEXT        NOT NULL,
    offset_value    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_event_links_source ON event_links(source_event_id);
CREATE INDEX idx_event_links_target ON event_links(target_event_id);