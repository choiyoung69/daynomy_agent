-- Additional Rust OIDC replay protection; apply alongside the original V1..V53 schema.
CREATE TABLE IF NOT EXISTS oauth_login_states (
    state_hash TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);
