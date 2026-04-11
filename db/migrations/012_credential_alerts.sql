CREATE TABLE credential_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_id   UUID NOT NULL REFERENCES credentials(id),
    alert_type      VARCHAR(20) NOT NULL CHECK (alert_type IN (
                        '30_day_warning', '60_day_warning', '90_day_warning', 'expired', 'custom'
                    )),
    alert_date      DATE NOT NULL,
    sent_at         TIMESTAMPTZ,
    sent_to_user_id UUID REFERENCES users(id),
    sent_via        VARCHAR(20),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ca_credential ON credential_alerts (credential_id);
CREATE INDEX idx_ca_pending ON credential_alerts (alert_date) WHERE sent_at IS NULL;
