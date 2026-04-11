CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    claim_id        UUID REFERENCES claims(id),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    ticket_type     VARCHAR(30) NOT NULL CHECK (ticket_type IN (
                        'coding_review', 'billing_review', 'missing_info',
                        'denial_appeal', 'credential_issue', 'general'
                    )),
    status          VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN (
                        'open', 'in_progress', 'blocked', 'resolved', 'closed'
                    )),
    priority        SMALLINT NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 5),
    assigned_to_id  UUID REFERENCES users(id),
    created_by_id   UUID NOT NULL REFERENCES users(id),
    due_date        DATE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_ticket_org ON tickets (organization_id);
CREATE INDEX idx_ticket_claim ON tickets (claim_id);
CREATE INDEX idx_ticket_assignee ON tickets (assigned_to_id)
    WHERE status NOT IN ('resolved', 'closed');
CREATE INDEX idx_ticket_status ON tickets (organization_id, status)
    WHERE deleted_at IS NULL;
CREATE INDEX idx_ticket_priority ON tickets (organization_id, priority)
    WHERE status NOT IN ('resolved', 'closed');
CREATE INDEX idx_ticket_due ON tickets (due_date)
    WHERE status NOT IN ('resolved', 'closed');
