CREATE TABLE claim_lines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    line_number     SMALLINT NOT NULL,
    cpt_code        VARCHAR(10),
    cpt_description VARCHAR(255),
    icd_codes       VARCHAR(10)[],
    modifier_codes  VARCHAR(5)[],
    units           SMALLINT NOT NULL DEFAULT 1,
    charge_amount   NUMERIC(10, 2),
    date_of_service DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (claim_id, line_number)
);

CREATE INDEX idx_cl_claim ON claim_lines (claim_id);
CREATE INDEX idx_cl_cpt ON claim_lines (cpt_code);
