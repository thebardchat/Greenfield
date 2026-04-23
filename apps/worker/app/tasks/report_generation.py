"""Report generation task — background CSV/summary export.

Supported report types:
  claims_csv        — All claims for org with status, amounts, facility, assignees
  productivity      — Per-biller/coder: claims processed, avg time, flagged rate
  denial_trends     — Top denial reasons + appeal success rate
  credentials_status — Credential expiry overview across org

Reports are written to uploads/reports/<org_id>/<report_type>_<date>.csv
and the file path is returned in the result dict.

Enqueue from the API via arq:
    await redis.enqueue_job("generate_report",
        report_type="claims_csv",
        organization_id="<uuid>",
        params={"date_from": "2026-01-01", "date_to": "2026-04-30"},
    )
"""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

import sqlalchemy as sa

from ._db import get_session

log = logging.getLogger(__name__)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
REPORTS_DIR = UPLOAD_DIR / "reports"


async def generate_report(
    ctx: dict,
    report_type: str,
    organization_id: str,
    params: dict,
) -> dict:
    """Generate a report and write it to disk.

    Args:
        report_type:     One of: claims_csv, productivity, denial_trends,
                         credentials_status
        organization_id: UUID of the organization to report on
        params:          Optional filters — date_from, date_to, facility_id

    Returns:
        {"status": "ok", "file_path": str, "row_count": int, "report_type": str}
    """
    date_from = params.get("date_from") or str(date(date.today().year, date.today().month, 1))
    date_to = params.get("date_to") or str(date.today())
    facility_id = params.get("facility_id")

    generators = {
        "claims_csv": _claims_csv,
        "productivity": _productivity,
        "denial_trends": _denial_trends,
        "credentials_status": _credentials_status,
    }

    if report_type not in generators:
        return {"status": "error", "error": f"Unknown report type: {report_type}"}

    Session = get_session()
    async with Session() as db:
        rows, headers = await generators[report_type](
            db, organization_id, date_from, date_to, facility_id
        )

    # Write CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    csv_content = output.getvalue()

    # Save to disk
    report_dir = REPORTS_DIR / organization_id
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_name = f"{report_type}_{ts}.csv"
    file_path = report_dir / file_name
    file_path.write_text(csv_content, encoding="utf-8")

    log.info(
        "[report] %s generated: %d rows → %s",
        report_type, len(rows), file_path,
    )
    return {
        "status": "ok",
        "report_type": report_type,
        "file_path": str(file_path),
        "row_count": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────── Report generators ───────────────────────────


async def _claims_csv(
    db, org_id: str, date_from: str, date_to: str, facility_id: str | None
) -> tuple[list, list]:
    """Full claim export with patient, facility, assignee info."""
    facility_filter = "AND c.facility_id = :facility_id" if facility_id else ""
    params: dict = {"org_id": org_id, "date_from": date_from, "date_to": date_to}
    if facility_id:
        params["facility_id"] = facility_id

    result = await db.execute(
        sa.text(f"""
            SELECT
                c.claim_number,
                c.status,
                c.form_type,
                c.date_of_service_from,
                c.date_of_service_to,
                c.provider_npi,
                c.total_charges,
                c.total_paid,
                c.place_of_service,
                c.flagged,
                c.flag_reason,
                c.priority,
                f.name AS facility_name,
                p.last_name || ', ' || p.first_name AS patient_name,
                p.date_of_birth AS patient_dob,
                p.primary_insurance_name AS insurance,
                coder.first_name || ' ' || coder.last_name AS assigned_coder,
                biller.first_name || ' ' || biller.last_name AS assigned_biller,
                c.created_at,
                c.updated_at
            FROM claims c
            LEFT JOIN facilities f ON f.id = c.facility_id
            LEFT JOIN patients p ON p.id = c.patient_id
            LEFT JOIN users coder ON coder.id = c.assigned_coder_id
            LEFT JOIN users biller ON biller.id = c.assigned_biller_id
            WHERE c.organization_id = :org_id
              AND c.deleted_at IS NULL
              AND c.created_at::date BETWEEN :date_from AND :date_to
              {facility_filter}
            ORDER BY c.created_at DESC
        """),
        params,
    )
    rows = [list(r._mapping.values()) for r in result.fetchall()]
    headers = [
        "Claim Number", "Status", "Form Type", "DOS From", "DOS To",
        "Provider NPI", "Total Charges", "Total Paid", "Place of Service",
        "Flagged", "Flag Reason", "Priority", "Facility", "Patient Name",
        "Patient DOB", "Insurance", "Assigned Coder", "Assigned Biller",
        "Created At", "Updated At",
    ]
    return rows, headers


async def _productivity(
    db, org_id: str, date_from: str, date_to: str, _facility_id: str | None
) -> tuple[list, list]:
    """Biller/coder throughput — claims processed, flagged rate, avg turnaround."""
    result = await db.execute(
        sa.text("""
            SELECT
                u.first_name || ' ' || u.last_name AS user_name,
                u.role,
                COUNT(DISTINCT CASE WHEN c.assigned_coder_id = u.id THEN c.id END)
                    AS claims_coded,
                COUNT(DISTINCT CASE WHEN c.assigned_biller_id = u.id THEN c.id END)
                    AS claims_billed,
                COUNT(DISTINCT CASE WHEN (c.assigned_coder_id = u.id
                                         OR c.assigned_biller_id = u.id)
                                         AND c.flagged = TRUE THEN c.id END)
                    AS flagged_claims,
                COUNT(DISTINCT t.id) AS tickets_worked,
                COUNT(DISTINCT CASE WHEN t.status = 'closed' THEN t.id END)
                    AS tickets_closed
            FROM users u
            LEFT JOIN claims c ON (c.assigned_coder_id = u.id
                                   OR c.assigned_biller_id = u.id)
                               AND c.deleted_at IS NULL
                               AND c.updated_at::date BETWEEN :date_from AND :date_to
            LEFT JOIN tickets t ON t.assigned_to_id = u.id
                               AND t.deleted_at IS NULL
                               AND t.updated_at::date BETWEEN :date_from AND :date_to
            WHERE u.organization_id = :org_id
              AND u.role IN ('biller', 'coder')
              AND u.deleted_at IS NULL
            GROUP BY u.id, u.first_name, u.last_name, u.role
            ORDER BY claims_coded + claims_billed DESC
        """),
        {"org_id": org_id, "date_from": date_from, "date_to": date_to},
    )
    rows = [list(r._mapping.values()) for r in result.fetchall()]
    headers = [
        "Name", "Role", "Claims Coded", "Claims Billed",
        "Flagged Claims", "Tickets Worked", "Tickets Closed",
    ]
    return rows, headers


async def _denial_trends(
    db, org_id: str, date_from: str, date_to: str, _facility_id: str | None
) -> tuple[list, list]:
    """Top denial reasons and appeal outcomes."""
    result = await db.execute(
        sa.text("""
            SELECT
                COALESCE(flag_reason, 'Unknown') AS denial_reason,
                COUNT(*) AS denial_count,
                COUNT(CASE WHEN status = 'appealed' THEN 1 END) AS appealed_count,
                COUNT(CASE WHEN status = 'paid' THEN 1 END) AS paid_after_appeal,
                ROUND(
                    100.0 * COUNT(CASE WHEN status = 'paid' THEN 1 END)
                    / NULLIF(COUNT(CASE WHEN status = 'appealed' THEN 1 END), 0),
                    1
                ) AS appeal_success_rate_pct,
                COALESCE(SUM(total_charges), 0) AS total_charges_at_risk,
                COALESCE(SUM(CASE WHEN status = 'paid' THEN total_paid ELSE 0 END), 0)
                    AS recovered_amount
            FROM claims
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND status IN ('denied', 'appealed', 'paid', 'void')
              AND updated_at::date BETWEEN :date_from AND :date_to
            GROUP BY flag_reason
            ORDER BY denial_count DESC
            LIMIT 50
        """),
        {"org_id": org_id, "date_from": date_from, "date_to": date_to},
    )
    rows = [list(r._mapping.values()) for r in result.fetchall()]
    headers = [
        "Denial Reason", "Denial Count", "Appealed Count",
        "Paid After Appeal", "Appeal Success %",
        "Total Charges At Risk", "Recovered Amount",
    ]
    return rows, headers


async def _credentials_status(
    db, org_id: str, _date_from: str, _date_to: str, _facility_id: str | None
) -> tuple[list, list]:
    """Full credential expiry overview across the organization."""
    result = await db.execute(
        sa.text("""
            SELECT
                c.provider_name,
                c.credential_type,
                c.credential_number,
                c.issuing_state,
                c.expiry_date,
                c.status,
                CASE
                    WHEN c.expiry_date IS NULL THEN NULL
                    ELSE (c.expiry_date - CURRENT_DATE)
                END AS days_until_expiry,
                f.name AS facility_name,
                COALESCE(
                    string_agg(ca.alert_type, ', ' ORDER BY ca.alert_type),
                    'none'
                ) AS alerts_generated
            FROM credentials c
            LEFT JOIN facilities f ON f.id = c.facility_id
            LEFT JOIN credential_alerts ca ON ca.credential_id = c.id
            WHERE c.organization_id = :org_id
              AND c.deleted_at IS NULL
            GROUP BY c.id, c.provider_name, c.credential_type,
                     c.credential_number, c.issuing_state, c.expiry_date,
                     c.status, f.name
            ORDER BY c.expiry_date ASC NULLS LAST
        """),
        {"org_id": org_id},
    )
    rows = [list(r._mapping.values()) for r in result.fetchall()]
    headers = [
        "Provider Name", "Credential Type", "Credential Number",
        "State", "Expiry Date", "Status", "Days Until Expiry",
        "Facility", "Alerts Generated",
    ]
    return rows, headers
