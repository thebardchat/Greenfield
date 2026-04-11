CREATE TABLE patients (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id),
    first_name              VARCHAR(100) NOT NULL,
    last_name               VARCHAR(100) NOT NULL,
    date_of_birth           DATE NOT NULL,
    mrn                     VARCHAR(50),
    ssn_last_four           VARCHAR(4),
    gender                  VARCHAR(10),
    primary_insurance_name  VARCHAR(255),
    primary_insurance_id    VARCHAR(50),
    secondary_insurance_name VARCHAR(255),
    secondary_insurance_id  VARCHAR(50),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ
);

CREATE INDEX idx_pat_org ON patients (organization_id);
CREATE INDEX idx_pat_mrn ON patients (organization_id, mrn) WHERE mrn IS NOT NULL;
CREATE INDEX idx_pat_name ON patients (organization_id, last_name, first_name);
CREATE INDEX idx_pat_dob ON patients (organization_id, date_of_birth);
