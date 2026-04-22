-- APPEND-ONLY: No UPDATE or DELETE ever permitted on this table.
-- This is the HIPAA compliance backbone.

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    session_id      VARCHAR(100),
    ip_address      INET,
    user_agent      TEXT,
    action          VARCHAR(50) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     UUID,
    old_values      JSONB,
    new_values      JSONB,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log (user_id, created_at);
CREATE INDEX idx_audit_org ON audit_log (organization_id, created_at);
CREATE INDEX idx_audit_resource ON audit_log (resource_type, resource_id);
CREATE INDEX idx_audit_action ON audit_log (action, created_at);
CREATE INDEX idx_audit_created ON audit_log (created_at);

-- Revoke DELETE and UPDATE from the application role.
-- Run this after creating the app user:
-- REVOKE UPDATE, DELETE ON audit_log FROM claimcruncher;
