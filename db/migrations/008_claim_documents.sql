CREATE TABLE claim_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID REFERENCES claims(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    uploaded_by_id  UUID NOT NULL REFERENCES users(id),
    file_name       VARCHAR(255) NOT NULL,
    file_path       TEXT NOT NULL,
    file_size_bytes BIGINT,
    mime_type       VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    storage_backend VARCHAR(20) NOT NULL DEFAULT 'local' CHECK (storage_backend IN ('local', 's3')),
    ocr_status      VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (ocr_status IN (
                        'pending', 'processing', 'completed', 'failed'
                    )),
    ocr_provider    VARCHAR(20),
    ocr_text        TEXT,
    ocr_structured  JSONB,
    ocr_confidence  NUMERIC(5, 4),
    ocr_completed_at TIMESTAMPTZ,
    page_count      SMALLINT,
    checksum_sha256 VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_doc_claim ON claim_documents (claim_id);
CREATE INDEX idx_doc_org ON claim_documents (organization_id);
CREATE INDEX idx_doc_ocr_pending ON claim_documents (ocr_status)
    WHERE ocr_status IN ('pending', 'processing');
CREATE INDEX idx_doc_checksum ON claim_documents (checksum_sha256);
