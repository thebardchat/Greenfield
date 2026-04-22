"""
OCR pipeline task — registered with arq worker.

Flow:
  1. Load document record from DB
  2. Locate file on disk (or S3)
  3. Run Tesseract (CPU-bound, via executor)
  4. If confidence < threshold → attempt cloud fallback (Document AI / Textract)
  5. Store OCR text + structured JSON back to claim_documents
  6. Update parent claim status: pending → under_review (if all docs done)
  7. Enqueue Cruncher auto-flag job (Haiku, fast)
  8. Index claim into RAG embeddings store

Error handling:
  - Each step is independently guarded; partial success is recorded.
  - Permanent failures (file missing, Tesseract crash) update ocr_status='failed'
    and do NOT retry automatically (arq max_tries=1 for this task).
  - Transient failures (DB timeout) raise and let arq retry (up to 3 times).
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from ..ocr import TesseractProvider, OcrResult, OcrStatus

log = logging.getLogger(__name__)

# ─────────────────────── DB helpers ──────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://claimcruncher:claimcruncher@localhost:5433/claimcruncher",
)

_engine = None
_Session = None


def _get_session() -> async_sessionmaker[AsyncSession]:
    global _engine, _Session
    if _Session is None:
        _engine = create_async_engine(DATABASE_URL, pool_size=5, max_overflow=10)
        _Session = async_sessionmaker(_engine, expire_on_commit=False)
    return _Session


# ─────────────────────── Constants ───────────────────────────────────

CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.85"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
CRUNCHER_AUTO_FLAG_TASK = "auto_flag_claim"


# ─────────────────────── Main task ───────────────────────────────────


async def process_document(ctx: dict, document_id: str) -> dict:
    """
    arq task entry point.

    Args:
        ctx:         arq context dict (contains redis pool, etc.)
        document_id: UUID of the claim_documents row to process.

    Returns:
        Summary dict with status, word_count, confidence, etc.
    """
    log.info("[OCR] Starting pipeline for document_id=%s", document_id)

    Session = _get_session()

    async with Session() as db:
        # ── 1. Load document record ──────────────────────────────────
        doc = await _load_document(db, document_id)
        if doc is None:
            log.error("[OCR] Document %s not found", document_id)
            return {"status": "error", "error": "document not found"}

        if doc["deleted_at"] is not None:
            log.warning("[OCR] Document %s is deleted — skipping", document_id)
            return {"status": "skipped", "reason": "deleted"}

        # ── 2. Mark as processing ────────────────────────────────────
        await _update_ocr_status(db, document_id, "processing")

        # ── 3. Locate file ───────────────────────────────────────────
        file_path = _resolve_file_path(doc)
        if file_path is None or not file_path.exists():
            log.error("[OCR] File not found on disk for document %s", document_id)
            await _update_ocr_status(db, document_id, "failed", error="file not found on disk")
            return {"status": "error", "error": "file not found"}

        # ── 4. Run Tesseract (blocking — run in executor) ─────────────
        provider = TesseractProvider()
        loop = asyncio.get_event_loop()
        result: OcrResult = await loop.run_in_executor(
            None,
            lambda: asyncio.run(provider.extract(file_path, doc["mime_type"] or "application/pdf")),
        )

        log.info(
            "[OCR] Tesseract done for %s: %d words, conf=%.3f, status=%s",
            document_id,
            result.word_count,
            result.confidence,
            result.status.value,
        )

        # ── 5. Cloud fallback if confidence below threshold ──────────
        if result.succeeded and result.confidence < CONFIDENCE_THRESHOLD:
            log.info(
                "[OCR] Confidence %.3f below threshold %.2f — checking cloud fallback",
                result.confidence,
                CONFIDENCE_THRESHOLD,
            )
            cloud_result = await _try_cloud_fallback(file_path, doc["mime_type"])
            if cloud_result and cloud_result.confidence > result.confidence:
                log.info(
                    "[OCR] Cloud fallback improved confidence: %.3f → %.3f",
                    result.confidence,
                    cloud_result.confidence,
                )
                result = cloud_result
            else:
                # Keep Tesseract result but mark as low confidence
                result.status = OcrStatus.LOW_CONFIDENCE

        # ── 6. Parse structured data via Cruncher (EOB parsing) ──────
        structured = None
        if result.succeeded and result.word_count >= 20:
            structured = await _parse_structured(result.text)

        # ── 7. Save OCR results to DB ────────────────────────────────
        final_status = "completed" if result.succeeded else "failed"
        await _save_ocr_results(
            db,
            document_id=document_id,
            ocr_text=result.text,
            structured=structured,
            status=final_status,
            confidence=result.confidence,
            page_count=result.page_count,
            provider=result.provider,
            error=result.error,
        )

        # ── 8. Update claim status if appropriate ────────────────────
        claim_id = doc.get("claim_id")
        if claim_id and result.succeeded:
            await _maybe_advance_claim_status(db, claim_id)

        # ── 9. Index into RAG ────────────────────────────────────────
        if claim_id and result.succeeded:
            await _index_claim_rag(db, claim_id)

        # ── 10. Enqueue auto-flag if OCR succeeded ───────────────────
        if claim_id and result.succeeded and ctx.get("redis"):
            await _enqueue_auto_flag(ctx["redis"], claim_id, result.text, structured)

    summary = result.summary()
    summary["document_id"] = document_id
    summary["claim_id"] = claim_id if claim_id else None
    log.info("[OCR] Pipeline complete: %s", summary)
    return summary


# ─────────────────────── DB helpers ──────────────────────────────────


async def _load_document(db: AsyncSession, document_id: str) -> dict | None:
    rows = await db.execute(
        sa.text("""
            SELECT id, claim_id, file_path, file_name, mime_type,
                   storage_backend, s3_key, deleted_at
            FROM claim_documents
            WHERE id = :id
        """),
        {"id": document_id},
    )
    row = rows.mappings().first()
    return dict(row) if row else None


async def _update_ocr_status(
    db: AsyncSession,
    document_id: str,
    status: str,
    error: str | None = None,
) -> None:
    await db.execute(
        sa.text("""
            UPDATE claim_documents
            SET ocr_status = :status,
                updated_at = NOW()
            WHERE id = :id
        """),
        {"status": status, "id": document_id},
    )
    await db.commit()


async def _save_ocr_results(
    db: AsyncSession,
    *,
    document_id: str,
    ocr_text: str,
    structured: dict | None,
    status: str,
    confidence: float,
    page_count: int,
    provider: str,
    error: str | None,
) -> None:
    import json

    await db.execute(
        sa.text("""
            UPDATE claim_documents
            SET ocr_status      = :status,
                ocr_text        = :ocr_text,
                ocr_structured  = :structured,
                updated_at      = NOW()
            WHERE id = :id
        """),
        {
            "id": document_id,
            "status": status,
            "ocr_text": ocr_text,
            "structured": json.dumps(structured) if structured else None,
        },
    )
    await db.commit()
    log.debug(
        "[OCR] Saved results: status=%s conf=%.3f pages=%d provider=%s",
        status,
        confidence,
        page_count,
        provider,
    )


async def _maybe_advance_claim_status(db: AsyncSession, claim_id: str) -> None:
    """
    If the claim is still 'pending' and it has at least one completed document,
    advance it to 'under_review' so billers can start working.
    """
    row = await db.execute(
        sa.text("SELECT status FROM claims WHERE id = :id"),
        {"id": claim_id},
    )
    claim = row.mappings().first()
    if not claim or claim["status"] != "pending":
        return

    await db.execute(
        sa.text("""
            UPDATE claims
            SET status     = 'under_review',
                updated_at = NOW()
            WHERE id = :id
              AND status   = 'pending'
        """),
        {"id": claim_id},
    )
    await db.commit()
    log.info("[OCR] Claim %s advanced: pending → under_review", claim_id)


# ─────────────────────── File location ───────────────────────────────


def _resolve_file_path(doc: dict) -> Path | None:
    """Return the local path to the document file, regardless of storage backend."""
    backend = doc.get("storage_backend", "local")
    if backend == "local":
        raw = doc.get("file_path") or doc.get("s3_key")
        if not raw:
            return None
        p = Path(raw)
        if p.is_absolute():
            return p
        return UPLOAD_DIR / p
    elif backend == "s3":
        # For S3 docs we'd download to tmp first; stub for now
        # Full implementation: boto3 / MinIO download to /tmp/{doc_id}
        log.warning("[OCR] S3 download not yet implemented for document %s", doc["id"])
        return None
    return None


# ─────────────────────── Cloud fallback (stub) ───────────────────────


async def _try_cloud_fallback(file_path: Path, mime_type: str) -> OcrResult | None:
    """
    Attempt cloud OCR (Google Document AI or AWS Textract).
    Returns None if no cloud provider is configured.

    To enable: set OCR_CLOUD_PROVIDER=document_ai|textract in .env
    and add the relevant credentials.
    """
    provider_name = os.getenv("OCR_CLOUD_PROVIDER", "none").lower()
    if provider_name == "none":
        return None

    if provider_name == "document_ai":
        # from .document_ai import DocumentAiProvider
        # return await DocumentAiProvider().extract(file_path, mime_type)
        log.info("[OCR] Document AI provider not yet wired — skipping cloud fallback")
        return None

    if provider_name == "textract":
        # from .textract import TextractProvider
        # return await TextractProvider().extract(file_path, mime_type)
        log.info("[OCR] Textract provider not yet wired — skipping cloud fallback")
        return None

    log.warning("[OCR] Unknown cloud provider: %s", provider_name)
    return None


# ─────────────────────── Structured parsing ──────────────────────────


async def _parse_structured(ocr_text: str) -> dict | None:
    """
    Call CruncherClient.parse_eob() to extract structured data from OCR text.
    Returns None if Cruncher is not configured or parsing fails.
    """
    try:
        import sys, os

        # CruncherClient lives in the services package (sibling repo directory)
        # Adjust sys.path so the worker can import it
        repo_root = Path(__file__).resolve().parents[5]
        services_path = repo_root / "services"
        if str(services_path) not in sys.path:
            sys.path.insert(0, str(services_path))

        from cruncher.client import CruncherClient

        client = CruncherClient()
        if not client.enabled:
            return None

        result = await client.parse_eob(ocr_text)
        return result
    except Exception as exc:  # noqa: BLE001
        log.warning("[OCR] EOB structured parsing failed: %s", exc)
        return None


# ─────────────────────── RAG indexing ────────────────────────────────


async def _index_claim_rag(db: AsyncSession, claim_id: str) -> None:
    """
    Build/update the RAG embedding for this claim so Cruncher chat
    can retrieve similar historical claims.
    """
    try:
        import sys
        repo_root = Path(__file__).resolve().parents[5]
        services_path = repo_root / "services"
        if str(services_path) not in sys.path:
            sys.path.insert(0, str(services_path))

        from cruncher.rag import ClaimRAG

        # Pull minimal claim + lines data for embedding
        claim_row = await db.execute(
            sa.text("""
                SELECT c.id, c.patient_id, c.payer_name, c.status,
                       c.total_charge, c.denial_reason,
                       json_agg(json_build_object(
                           'cpt_code', cl.cpt_code,
                           'description', cl.description,
                           'units', cl.units,
                           'charge_amount', cl.charge_amount
                       )) FILTER (WHERE cl.id IS NOT NULL) AS lines
                FROM claims c
                LEFT JOIN claim_lines cl ON cl.claim_id = c.id AND cl.deleted_at IS NULL
                WHERE c.id = :id
                GROUP BY c.id
            """),
            {"id": claim_id},
        )
        claim_data = claim_row.mappings().first()
        if not claim_data:
            return

        rag = ClaimRAG(db)
        await rag.ensure_table()
        claim_dict = dict(claim_data)
        lines = claim_dict.pop("lines") or []
        await rag.index_claim(claim_id, claim_dict, lines)
        log.info("[OCR] RAG index updated for claim %s", claim_id)

    except Exception as exc:  # noqa: BLE001
        log.warning("[OCR] RAG indexing failed for claim %s: %s", claim_id, exc)


# ─────────────────────── Auto-flag enqueue ───────────────────────────


async def _enqueue_auto_flag(redis, claim_id: str, ocr_text: str, structured: dict | None) -> None:
    """
    Push an auto_flag_claim job onto the arq queue.
    Haiku will review OCR text + structured data and flag billing issues.
    """
    try:
        from arq import create_pool, RedisSettings

        pool = await create_pool(RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://localhost:6380/0")))
        await pool.enqueue_job(
            CRUNCHER_AUTO_FLAG_TASK,
            claim_id,
            ocr_text[:8000],   # trim to avoid huge payloads
            structured or {},
        )
        await pool.aclose()
        log.info("[OCR] Enqueued auto-flag for claim %s", claim_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("[OCR] Failed to enqueue auto-flag for claim %s: %s", claim_id, exc)
