"""Documents router — file upload, download, OCR results.

Endpoints:
  POST   /api/documents/upload              — Upload PDF/image, store, enqueue OCR
  GET    /api/documents/{id}                — Get document metadata
  GET    /api/documents/{id}/download       — Serve file (RBAC enforced)
  GET    /api/documents/{id}/ocr            — Get OCR text + structured data
  DELETE /api/documents/{id}               — Soft delete (org_admin+)

Storage backends:
  local — files saved to settings.upload_dir, served directly
  s3    — files stored in MinIO/S3, served via presigned URL

OCR is enqueued as an async job. The worker processes it and updates
claim_documents.ocr_status, ocr_text, ocr_structured, ocr_confidence.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.user import User

router = APIRouter()

# Allowed MIME types
ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/webp",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _local_path(file_path: str) -> Path:
    return Path(settings.upload_dir) / file_path


async def _store_local(file_data: bytes, rel_path: str) -> None:
    full_path = _local_path(rel_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(file_data)


async def _store_s3(file_data: bytes, rel_path: str, mime_type: str) -> None:
    """Upload to MinIO/S3."""
    import aioboto3  # type: ignore
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    ) as s3:
        await s3.put_object(
            Bucket=settings.s3_bucket,
            Key=rel_path,
            Body=file_data,
            ContentType=mime_type,
        )


async def _presigned_url(rel_path: str, expires: int = 3600) -> str:
    import aioboto3  # type: ignore
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    ) as s3:
        return await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": rel_path},
            ExpiresIn=expires,
        )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DocumentResponse(BaseModel):
    id: str
    claim_id: str | None
    organization_id: str
    file_name: str
    file_size_bytes: int | None
    mime_type: str
    storage_backend: str
    ocr_status: str
    ocr_provider: str | None
    ocr_confidence: float | None
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OCRResultResponse(BaseModel):
    document_id: str
    ocr_status: str
    ocr_text: str | None
    ocr_structured: dict | None
    ocr_confidence: float | None
    ocr_completed_at: datetime | None


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    claim_id: str | None = Form(None),
    current_user: User = Depends(require_permission("documents:upload")),
    db: AsyncSession = Depends(get_db),
):
    """Upload a claim document (PDF, image).

    Computes SHA-256 checksum, deduplicates by hash, stores file,
    creates claim_documents record, and enqueues OCR job.

    Returns the document metadata including its ID for polling OCR status.
    """
    org_id = str(current_user.organization_id) if current_user.organization_id else None
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must belong to an organization to upload documents",
        )

    # Validate file type
    mime = file.content_type or "application/octet-stream"
    if mime not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {mime}. Allowed: PDF, PNG, JPEG, TIFF, WEBP",
        )

    # Read file
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(data) // 1024 // 1024}MB). Maximum: 50MB",
        )

    # Compute checksum
    checksum = hashlib.sha256(data).hexdigest()

    # Check for duplicate within org
    existing = await db.execute(
        text(
            "SELECT id FROM claim_documents "
            "WHERE organization_id = :org_id AND checksum_sha256 = :hash AND deleted_at IS NULL"
        ).bindparams(org_id=org_id, hash=checksum)
    )
    dup = existing.scalar_one_or_none()
    if dup:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate file detected (document ID: {dup}). This file is already uploaded.",
        )

    # Build relative storage path: org_id/YYYY/MM/doc_id.ext
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    ext = Path(file.filename or "document.pdf").suffix.lower() or ".pdf"
    rel_path = f"{org_id}/{now.year}/{now.month:02d}/{doc_id}{ext}"

    # Store file
    backend = settings.storage_backend
    if backend == "s3":
        await _store_s3(data, rel_path, mime)
    else:
        await _store_local(data, rel_path)

    # Insert claim_documents record
    await db.execute(
        text(
            "INSERT INTO claim_documents "
            "(id, claim_id, organization_id, uploaded_by_id, file_name, file_path, "
            "file_size_bytes, mime_type, storage_backend, ocr_status, checksum_sha256, "
            "created_at, updated_at) "
            "VALUES (:id, :claim_id, :org_id, :user_id, :name, :path, :size, :mime, "
            ":backend, 'pending', :hash, :now, :now)"
        ).bindparams(
            id=doc_id,
            claim_id=claim_id,
            org_id=org_id,
            user_id=str(current_user.id),
            name=file.filename or f"document{ext}",
            path=rel_path,
            size=len(data),
            mime=mime,
            backend=backend,
            hash=checksum,
            now=now,
        )
    )
    await db.commit()

    # Enqueue OCR job (fire-and-forget via Redis/arq)
    await _enqueue_ocr(doc_id)

    return {
        "document_id": doc_id,
        "file_name": file.filename,
        "file_size_bytes": len(data),
        "mime_type": mime,
        "storage_backend": backend,
        "ocr_status": "pending",
        "checksum_sha256": checksum,
        "claim_id": claim_id,
        "created_at": now.isoformat(),
    }


async def _enqueue_ocr(document_id: str) -> None:
    """Enqueue an OCR job for the document via Redis/arq."""
    try:
        import redis.asyncio as aioredis  # type: ignore
        import json

        r = await aioredis.from_url(settings.redis_url)
        await r.lpush(
            "arq:queue",
            json.dumps({
                "function": "process_document",
                "args": [document_id],
                "kwargs": {},
            }),
        )
        await r.aclose()
    except Exception:
        # Don't fail the upload if Redis is down — OCR can be triggered manually
        pass


# ---------------------------------------------------------------------------
# Get metadata
# ---------------------------------------------------------------------------


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(require_permission("documents:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get document metadata (not the file content)."""
    doc = await _fetch_doc(document_id, current_user, db)
    return doc


# ---------------------------------------------------------------------------
# Download file
# ---------------------------------------------------------------------------


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: User = Depends(require_permission("documents:read")),
    db: AsyncSession = Depends(get_db),
):
    """Serve the document file. RBAC enforced at the endpoint level.

    For local storage: streams the file directly.
    For S3 storage: redirects to a time-limited presigned URL.
    """
    doc = await _fetch_doc(document_id, current_user, db)
    backend = doc["storage_backend"]
    file_path = doc["file_path"]

    if backend == "s3":
        url = await _presigned_url(file_path)
        return RedirectResponse(url=url)
    else:
        full_path = _local_path(file_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        return FileResponse(
            path=str(full_path),
            filename=doc["file_name"],
            media_type=doc["mime_type"],
        )


# ---------------------------------------------------------------------------
# OCR results
# ---------------------------------------------------------------------------


@router.get("/{document_id}/ocr")
async def get_ocr_results(
    document_id: str,
    current_user: User = Depends(require_permission("documents:read")),
    db: AsyncSession = Depends(get_db),
):
    """Return OCR text, structured data, and confidence score.

    Poll this endpoint to check OCR status. Status values:
      pending     — queued, not yet started
      processing  — OCR worker is running
      completed   — OCR done, text + structured data available
      failed      — OCR failed, check worker logs
    """
    row = await db.execute(
        text(
            "SELECT id, ocr_status, ocr_text, ocr_structured, "
            "ocr_confidence, ocr_completed_at "
            "FROM claim_documents WHERE id = :id AND deleted_at IS NULL"
        ).bindparams(id=document_id)
    )
    doc = row.fetchone()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": document_id,
        "ocr_status": doc.ocr_status,
        "ocr_text": doc.ocr_text,
        "ocr_structured": doc.ocr_structured,
        "ocr_confidence": float(doc.ocr_confidence) if doc.ocr_confidence else None,
        "ocr_completed_at": doc.ocr_completed_at.isoformat() if doc.ocr_completed_at else None,
    }


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_permission("documents:upload")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a document (sets deleted_at). Does not remove the file."""
    await _fetch_doc(document_id, current_user, db)  # Verify access
    await db.execute(
        text(
            "UPDATE claim_documents SET deleted_at = :now WHERE id = :id"
        ).bindparams(now=datetime.now(timezone.utc), id=document_id)
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def _fetch_doc(document_id: str, current_user: User, db: AsyncSession) -> dict:
    org_id = str(current_user.organization_id) if current_user.organization_id else None
    row = await db.execute(
        text(
            "SELECT id, claim_id, organization_id, file_name, file_path, "
            "file_size_bytes, mime_type, storage_backend, ocr_status, "
            "ocr_provider, ocr_confidence, page_count, created_at "
            "FROM claim_documents "
            "WHERE id = :id AND deleted_at IS NULL"
        ).bindparams(id=document_id)
    )
    doc = row.fetchone()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # Org-scope enforcement (super_admin sees all)
    if current_user.role != "super_admin" and str(doc.organization_id) != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return dict(doc._mapping)
