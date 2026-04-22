CREATE TABLE facilities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    facility_type   VARCHAR(50) CHECK (facility_type IN (
                        'hospital', 'clinic', 'snf', 'home_health', 'ambulatory', 'other'
                    )),
    address         TEXT,
    city            VARCHAR(100),
    state           VARCHAR(2),
    zip             VARCHAR(10),
    phone           VARCHAR(20),
    npi             VARCHAR(10),
    tax_id          VARCHAR(20),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_fac_org ON facilities (organization_id);
CREATE INDEX idx_fac_state ON facilities (state);
CREATE INDEX idx_fac_npi ON facilities (npi) WHERE npi IS NOT NULL;
