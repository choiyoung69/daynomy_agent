-- Native OAuth uses a PKCE-bound, single-use 60 second handoff. Only hashes persist.
CREATE TABLE mobile_auth_codes (
    code_hash char(64) PRIMARY KEY,
    member_id bigint NOT NULL REFERENCES members(id),
    code_challenge varchar(43) NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_mobile_auth_codes_expiry ON mobile_auth_codes(expires_at);
