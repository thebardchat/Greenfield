"""Reports router — analytics and exports for billing managers.

Endpoints:
  GET /api/reports/claims-summary      — Claim counts/amounts by status + facility
  GET /api/reports/productivity        — Biller/coder throughput over date range
  GET /api/reports/credentials-status  — Credential expiry overview across org
  GET /api/reports/export              — CSV export of claims (filtered)
  GET /api/reports/denial-trends       — Top denial reasons + dispute success rate

All endpoints are org-scoped and require reports:read permission.
Date range defaults to current month. All money in USD.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import require_permission
from app.models.user import User

router = APIRouter()


def _month_start() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


# ---------------------------------------------------------------------------
# Claims Summary
# ---------------------------------------------------------------------------


@router.get("/claims-summary")
async def claims_summary(
    date_from: date = Query(default_factory=_month_start),
    date_to: date = Query(default_factory=date.today),
    facility_id: str | None = Query(None),
    current_user: User = Depends(require_permission("reports:read")),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate claim statistics by status and (optionally) facility.

    Returns:
      - Count + total_charges + total_paid per status
      - Overall totals
      - Flagged claim count
      - Denial + appeal breakdown
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None

    params: dict[str, Any] = {
        "org_id": org_id,
        "date_from": date_from,
        "date_to": date_to,
    }
    facility_filter = ""
    if facility_id:
        facility_filter = "AND facility_id = :facility_id"
        params["facility_id"] = facility_id

    # Status breakdown
    status_rows = await db.execute(
        text(f"""
            SELECT
                status,
                COUNT(*) AS claim_count,
                COALESCE(SUM(total_charges), 0) AS total_charges,
                COALESCE(SUM(total_paid), 0) AS total_paid
            FROM claims
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND created_at::date BETWEEN :date_from AND :date_to
              {facility_filter}
            GROUP BY status
            ORDER BY status
        """).bindparams(**params)
    )

    by_status = [
        {
            "status": row.status,
            "claim_count": row.claim_count,
            "total_charges": float(row.total_charges),
            "total_paid": float(row.total_paid),
        }
        for row in status_rows.fetchall()
    ]

    # Totals
    total_row = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total_claims,
                COALESCE(SUM(total_charges), 0) AS total_charges,
                COALESCE(SUM(total_paid), 0) AS total_paid,
                SUM(CASE WHEN flagged THEN 1 ELSE 0 END) AS flagged_count,
                SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) AS denied_count,
                SUM(CASE WHEN status = 'appealed' THEN 1 ELSE 0 END) AS appealed_count
            FROM claims
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND created_at::date BETWEEN :date_from AND :date_to
              {facility_filter}
        """).bindparams(**params)
    ).fetchone()

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "facility_id": facility_id,
        "by_status": by_status,
        "totals": {
            "total_claims": total_row.total_claims,
            "total_charges": float(total_row.total_charges),
            "total_paid": float(total_row.total_paid),
            "collection_rate": (
                round(float(total_row.total_paid) / float(total_row.total_charges) * 100, 1)
                if total_row.total_charges and float(total_row.total_charges) > 0
                else 0.0
            ),
            "flagged_count": total_row.flagged_count,
            "denied_count": total_row.denied_count,
            "appealed_count": total_row.appealed_count,
            "denial_rate": (
                round(total_row.denied_count / total_row.total_claims * 100, 1)
                if total_row.total_claims > 0
                else 0.0
            ),
        },
    }


# ---------------------------------------------------------------------------
# Productivity Report
# ---------------------------------------------------------------------------


@router.get("/productivity")
async def productivity_report(
    date_from: date = Query(default_factory=_month_start),
    date_to: date = Query(default_factory=date.today),
    current_user: User = Depends(require_permission("reports:read")),
    db: AsyncSession = Depends(get_db),
):
    """Biller and coder throughput — claims processed per user per day.

    Returns per-user stats: claims coded, claims billed, avg time to code,
    flagged rate, and daily activity breakdown.
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None

    rows = await db.execute(
        text("""
            SELECT
                u.id AS user_id,
                u.first_name || ' ' || u.last_name AS full_name,
                u.role,
                SUM(CASE WHEN c.assigned_coder_id = u.id AND c.status IN ('coded','billed','paid') THEN 1 ELSE 0 END) AS claims_coded,
                SUM(CASE WHEN c.assigned_biller_id = u.id AND c.status IN ('billed','paid') THEN 1 ELSE 0 END) AS claims_billed,
                SUM(CASE WHEN (c.assigned_coder_id = u.id OR c.assigned_biller_id = u.id) AND c.flagged THEN 1 ELSE 0 END) AS flagged_claims,
                COUNT(DISTINCT CASE WHEN c.assigned_coder_id = u.id OR c.assigned_biller_id = u.id THEN c.id END) AS total_assigned
            FROM users u
            LEFT JOIN claims c ON (c.assigned_coder_id = u.id OR c.assigned_biller_id = u.id)
              AND c.organization_id = :org_id
              AND c.deleted_at IS NULL
              AND c.updated_at::date BETWEEN :date_from AND :date_to
            WHERE u.organization_id = :org_id
              AND u.is_active = TRUE
              AND u.deleted_at IS NULL
              AND u.role IN ('biller', 'coder', 'org_admin')
            GROUP BY u.id, u.first_name, u.last_name, u.role
            ORDER BY total_assigned DESC
        """).bindparams(org_id=org_id, date_from=date_from, date_to=date_to)
    )

    staff = []
    for row in rows.fetchall():
        total = row.total_assigned or 0
        flagged = row.flagged_claims or 0
        staff.append({
            "user_id": str(row.user_id),
            "full_name": row.full_name,
            "role": row.role,
            "claims_coded": row.claims_coded,
            "claims_billed": row.claims_billed,
            "total_assigned": total,
            "flagged_count": flagged,
            "flag_rate": round(flagged / total * 100, 1) if total > 0 else 0.0,
        })

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "staff": staff,
        "org_id": org_id,
    }


# ---------------------------------------------------------------------------
# Credentials Status
# ---------------------------------------------------------------------------


@router.get("/credentials-status")
async def credentials_status(
    days_ahead: int = Query(90, ge=1, le=365),
    current_user: User = Depends(require_permission("reports:read")),
    db: AsyncSession = Depends(get_db),
):
    """Credential expiry overview — what's expiring in the next N days.

    Returns expired, expiring-soon, and active counts per credential type,
    plus a list of actionable items sorted by urgency.
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None

    rows = await db.execute(
        text("""
            SELECT
                credential_type,
                provider_name,
                expiry_date,
                status,
                CASE
                    WHEN expiry_date < CURRENT_DATE THEN 'expired'
                    WHEN expiry_date <= CURRENT_DATE + INTERVAL ':days days' THEN 'expiring_soon'
                    ELSE 'active'
                END AS urgency
            FROM credentials
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
            ORDER BY expiry_date ASC NULLS LAST
        """).bindparams(org_id=org_id, days=days_ahead)
    )

    items = []
    counts = {"expired": 0, "expiring_soon": 0, "active": 0, "no_expiry": 0}
    for row in rows.fetchall():
        urgency = row.urgency or ("no_expiry" if row.expiry_date is None else "active")
        counts[urgency] = counts.get(urgency, 0) + 1
        if urgency in ("expired", "expiring_soon"):
            items.append({
                "credential_type": row.credential_type,
                "provider_name": row.provider_name,
                "expiry_date": str(row.expiry_date) if row.expiry_date else None,
                "status": row.status,
                "urgency": urgency,
            })

    return {
        "days_ahead": days_ahead,
        "summary": counts,
        "action_items": items,
        "as_of": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# Denial Trends
# ---------------------------------------------------------------------------


@router.get("/denial-trends")
async def denial_trends(
    date_from: date = Query(default_factory=_month_start),
    date_to: date = Query(default_factory=date.today),
    current_user: User = Depends(require_permission("reports:read")),
    db: AsyncSession = Depends(get_db),
):
    """Top denial reasons and appeal outcomes over a date range.

    Shows which denial reasons are most common and which are being
    successfully appealed — helps prioritize process improvements.
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None

    rows = await db.execute(
        text("""
            SELECT
                flag_reason,
                COUNT(*) AS denial_count,
                SUM(CASE WHEN status = 'appealed' THEN 1 ELSE 0 END) AS appealed,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) AS recovered
            FROM claims
            WHERE organization_id = :org_id
              AND deleted_at IS NULL
              AND status IN ('denied', 'appealed', 'paid')
              AND flagged = TRUE
              AND created_at::date BETWEEN :date_from AND :date_to
            GROUP BY flag_reason
            ORDER BY denial_count DESC
            LIMIT 20
        """).bindparams(org_id=org_id, date_from=date_from, date_to=date_to)
    )

    trends = []
    for row in rows.fetchall():
        trends.append({
            "denial_reason": row.flag_reason or "(unspecified)",
            "count": row.denial_count,
            "appealed": row.appealed,
            "recovered": row.recovered,
            "appeal_rate": round(row.appealed / row.denial_count * 100, 1) if row.denial_count else 0,
        })

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "trends": trends,
    }


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------


@router.get("/export")
async def export_report(
    date_from: date = Query(default_factory=_month_start),
    date_to: date = Query(default_factory=date.today),
    status_filter: str | None = Query(None, description="Comma-separated statuses to include"),
    facility_id: str | None = Query(None),
    flagged_only: bool = Query(False),
    current_user: User = Depends(require_permission("reports:read")),
    db: AsyncSession = Depends(get_db),
):
    """Export claims as CSV for billing software import.

    Includes: claim_number, patient MRN, facility, status, dates of service,
    charges, paid, provider NPI, assigned coder/biller, flag status.
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None

    conditions = [
        "c.organization_id = :org_id",
        "c.deleted_at IS NULL",
        "c.created_at::date BETWEEN :date_from AND :date_to",
    ]
    params: dict[str, Any] = {
        "org_id": org_id,
        "date_from": date_from,
        "date_to": date_to,
    }

    if flagged_only:
        conditions.append("c.flagged = TRUE")

    if facility_id:
        conditions.append("c.facility_id = :facility_id")
        params["facility_id"] = facility_id

    statuses = [s.strip() for s in (status_filter or "").split(",") if s.strip()]
    if statuses:
        # Build IN clause safely
        placeholders = ", ".join(f":s{i}" for i in range(len(statuses)))
        conditions.append(f"c.status IN ({placeholders})")
        for i, s in enumerate(statuses):
            params[f"s{i}"] = s

    where_clause = " AND ".join(conditions)

    rows = await db.execute(
        text(f"""
            SELECT
                c.claim_number,
                p.mrn AS patient_mrn,
                p.last_name || ', ' || p.first_name AS patient_name,
                f.name AS facility_name,
                c.status,
                c.form_type,
                c.date_of_service_from,
                c.date_of_service_to,
                c.total_charges,
                c.total_paid,
                c.provider_npi,
                c.referring_npi,
                c.place_of_service,
                c.flagged,
                c.flag_reason,
                c.priority,
                coder.first_name || ' ' || coder.last_name AS assigned_coder,
                biller.first_name || ' ' || biller.last_name AS assigned_biller,
                c.created_at
            FROM claims c
            LEFT JOIN patients p ON c.patient_id = p.id
            LEFT JOIN facilities f ON c.facility_id = f.id
            LEFT JOIN users coder ON c.assigned_coder_id = coder.id
            LEFT JOIN users biller ON c.assigned_biller_id = biller.id
            WHERE {where_clause}
            ORDER BY c.created_at DESC
        """).bindparams(**params)
    )

    # Stream CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "claim_number", "patient_mrn", "patient_name", "facility",
        "status", "form_type", "dos_from", "dos_to",
        "total_charges", "total_paid", "provider_npi", "referring_npi",
        "place_of_service", "flagged", "flag_reason", "priority",
        "assigned_coder", "assigned_biller", "created_at",
    ])
    for row in rows.fetchall():
        writer.writerow([
            row.claim_number, row.patient_mrn, row.patient_name, row.facility_name,
            row.status, row.form_type,
            str(row.date_of_service_from) if row.date_of_service_from else "",
            str(row.date_of_service_to) if row.date_of_service_to else "",
            str(row.total_charges) if row.total_charges else "0.00",
            str(row.total_paid) if row.total_paid else "0.00",
            row.provider_npi, row.referring_npi, row.place_of_service,
            "YES" if row.flagged else "NO", row.flag_reason or "", row.priority,
            row.assigned_coder or "", row.assigned_biller or "",
            row.created_at.isoformat() if row.created_at else "",
        ])

    filename = f"claims-export-{date_from}-to-{date_to}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
