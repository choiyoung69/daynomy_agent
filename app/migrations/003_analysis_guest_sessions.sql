-- Only opaque, random session identifiers are stored; no cookie contents or
-- portfolio payloads are written to logs. A failed provider call releases its
-- lease and does not consume the one successful guest trial.
CREATE TABLE IF NOT EXISTS analysis_guest_sessions (
    id UUID PRIMARY KEY,
    consumed BOOLEAN NOT NULL DEFAULT FALSE,
    request_token UUID,
    request_expires_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((request_token IS NULL) = (request_expires_at IS NULL))
);
