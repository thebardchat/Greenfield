CREATE TABLE credentials (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organizations(id),
    facility_id       UUID REFERENCES facilities(id),
    provider_name     VARCHAR(255) NOT NULL,
    credential_type   VARCHAR(30) NOT NULL CHECK (credential_type IN (
                          'npi', 'state_license', 'dea', 'board_cert',
                          'caqh', 'medicare', 'medicaid', 'commercial_payer', 'other'
                      )),
    credential_number VARCHAR(100) NOT NULL,
    issuing_state     VARCHAR(2),
    issued_date       DATE,
    expiry_date       DATE,
    status            VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN (
                          'active', 'expiring_soon', 'expired', 'revoked', 'pending'
                      )),
    document_path     TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ
);

CREATE INDEX idx_cred_org ON credentials (organization_id);
CREATE INDEX idx_cred_facility ON credentials (facility_id);
CREATE INDEX idx_cred_expiry ON credentials (expiry_date)
    WHERE status IN ('active', 'expiring_soon');
CREATE INDEX idx_cred_type ON credentials (credential_type);
CREATE INDEX idx_cred_provider ON credentials (organization_id, provider_name);
