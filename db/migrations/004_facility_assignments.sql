CREATE TABLE facility_assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id     UUID NOT NULL REFERENCES facilities(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    role            VARCHAR(20) NOT NULL CHECK (role IN ('biller', 'coder', 'lead', 'backup')),
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_fa_active ON facility_assignments (facility_id, user_id, role)
    WHERE effective_to IS NULL;
CREATE INDEX idx_fa_facility ON facility_assignments (facility_id);
CREATE INDEX idx_fa_user ON facility_assignments (user_id);
CREATE INDEX idx_fa_active ON facility_assignments (facility_id, role)
    WHERE effective_to IS NULL;
