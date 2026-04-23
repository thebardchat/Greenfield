"""Credential expiry checker — runs daily via arq cron.

Scans the credentials table for upcoming expirations and:
  1. Creates credential_alert records for 90/60/30-day and expired milestones
  2. Updates credential.status to 'expiring_soon' (≤30 days) or 'expired'
  3. Returns a summary of what was created/updated

Run schedule: daily at 07:00 UTC (configured in WorkerSettings.cron_jobs).
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa

from ._db import get_session

log = logging.getLogger(__name__)

# Days-before-expiry that trigger each alert milestone
ALERT_WINDOWS: dict[str, int] = {
    "90_day_warning": 90,
    "60_day_warning": 60,
    "30_day_warning": 30,
}


async def check_credential_expiry(ctx: dict) -> dict:
    """Scan all org credentials and create alerts for upcoming expirations.

    Creates at most one alert per (credential_id, alert_type). Idempotent —
    safe to run multiple times; duplicate alerts are never created.

    Returns summary: {created_alerts, expired_updated, expiring_soon_updated}
    """
    today = date.today()
    ninety_days_out = today + timedelta(days=90)

    stats = {"created_alerts": 0, "expired_updated": 0, "expiring_soon_updated": 0}

    Session = get_session()
    async with Session() as db:
        # ── 1. Load all active credentials expiring within 90 days ──
        rows = await db.execute(
            sa.text("""
                SELECT id, organization_id, provider_name, credential_type,
                       credential_number, expiry_date, status
                FROM credentials
                WHERE deleted_at IS NULL
                  AND expiry_date IS NOT NULL
                  AND expiry_date <= :ninety_days_out
                ORDER BY expiry_date ASC
            """),
            {"ninety_days_out": ninety_days_out},
        )
        credentials = [dict(r._mapping) for r in rows.fetchall()]
        log.info("[expiry] Found %d credentials expiring within 90 days", len(credentials))

        for cred in credentials:
            cred_id = str(cred["id"])
            expiry = cred["expiry_date"]
            days_left = (expiry - today).days

            # ── 2. Determine new status ─────────────────────────────
            if days_left < 0:
                new_status = "expired"
            elif days_left <= 30:
                new_status = "expiring_soon"
            else:
                new_status = cred["status"]  # keep current

            if new_status != cred["status"]:
                await db.execute(
                    sa.text("""
                        UPDATE credentials
                        SET status = :status, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"status": new_status, "id": cred_id},
                )
                if new_status == "expired":
                    stats["expired_updated"] += 1
                else:
                    stats["expiring_soon_updated"] += 1
                log.info(
                    "[expiry] %s %s → %s (expires %s, %d days)",
                    cred["provider_name"],
                    cred["credential_type"],
                    new_status,
                    expiry,
                    days_left,
                )

            # ── 3. Create expired alert if past ─────────────────────
            if days_left < 0:
                await _maybe_create_alert(db, cred_id, "expired", today, stats)
                await db.commit()
                continue

            # ── 4. Create milestone alerts (90/60/30-day) ───────────
            for alert_type, window in ALERT_WINDOWS.items():
                if days_left <= window:
                    await _maybe_create_alert(db, cred_id, alert_type, today, stats)

            await db.commit()

        log.info("[expiry] Done: %s", stats)

    return stats


async def _maybe_create_alert(
    db,
    credential_id: str,
    alert_type: str,
    today: date,
    stats: dict,
) -> None:
    """Insert alert only if one doesn't already exist for this milestone."""
    existing = await db.execute(
        sa.text("""
            SELECT id FROM credential_alerts
            WHERE credential_id = :cred_id AND alert_type = :type
        """),
        {"cred_id": credential_id, "type": alert_type},
    )
    if existing.fetchone() is not None:
        return  # already created for this milestone

    await db.execute(
        sa.text("""
            INSERT INTO credential_alerts
                (id, credential_id, alert_type, alert_date)
            VALUES
                (:id, :cred_id, :type, :alert_date)
        """),
        {
            "id": str(uuid4()),
            "cred_id": credential_id,
            "type": alert_type,
            "alert_date": today,
        },
    )
    stats["created_alerts"] += 1
    log.debug("[expiry] Created %s alert for credential %s", alert_type, credential_id)
