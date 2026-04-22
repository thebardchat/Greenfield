CREATE TABLE claims (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id),
    facility_id             UUID NOT NULL REFERENCES facilities(id),
    patient_id              UUID NOT NULL REFERENCES patients(id),
    claim_number            VARCHAR(50) UNIQUE,
    form_type               VARCHAR(20) CHECK (form_type IN ('cms_1500', 'ub_04', 'ada', 'other')),
    status                  VARCHAR(30) NOT NULL DEFAULT 'submitted' CHECK (status IN (
                                'submitted', 'ocr_processing', 'ocr_failed',
                                'ready_for_review', 'in_progress', 'coded',
                                'billed', 'paid', 'denied', 'appealed', 'void'
                            )),
    date_of_service_from    DATE,
    date_of_service_to      DATE,
    total_charges           NUMERIC(12, 2),
    total_paid              NUMERIC(12, 2) DEFAULT 0,
    provider_npi            VARCHAR(10),
    referring_npi           VARCHAR(10),
    place_of_service        VARCHAR(5),
    assigned_coder_id       UUID REFERENCES users(id),
    assigned_biller_id      UUID REFERENCES users(id),
    submitted_by_id         UUID REFERENCES users(id),
    notes                   TEXT,
    flagged                 BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason             TEXT,
    priority                SMALLINT NOT NULL DEFAULT 0 CHECK (priority BETWEEN 0 AND 5),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ
);

CREATE INDEX idx_claim_org ON claims (organization_id);
CREATE INDEX idx_claim_facility ON claims (facility_id);
CREATE INDEX idx_claim_patient ON claims (patient_id);
CREATE INDEX idx_claim_status ON claims (organization_id, status) WHERE deleted_at IS NULL;
CREATE INDEX idx_claim_dos ON claims (date_of_service_from);
CREATE INDEX idx_claim_coder ON claims (assigned_coder_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_claim_biller ON claims (assigned_biller_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_claim_number ON claims (claim_number) WHERE claim_number IS NOT NULL;
CREATE INDEX idx_claim_flagged ON claims (organization_id) WHERE flagged = TRUE AND deleted_at IS NULL;
