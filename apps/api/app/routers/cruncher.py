"""Cruncher router — Claude AI endpoints for Claim Cruncher.

Endpoints:
  POST /api/cruncher/chat              — Streaming assistant (SSE)
  POST /api/cruncher/analyze-claim/{id} — Full claim analysis
  POST /api/cruncher/denial-analysis/{id} — Denial + appeal strategy
  POST /api/cruncher/parse-eob         — Extract fields from EOB OCR text

All endpoints require authentication and cruncher:chat permission.
Tool execution is handled here (DB access lives in the router layer).
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.claim import Claim
from app.models.user import User
from app.safety.baa_check import require_baa

# Shared package path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "services"))

from cruncher.client import CruncherClient, ToolExecutor
from cruncher.rag import ClaimRAG

router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton client (initialized lazily)
# ---------------------------------------------------------------------------

_client: CruncherClient | None = None


def get_cruncher_client() -> CruncherClient:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cruncher AI is not configured — ANTHROPIC_API_KEY missing",
            )
        _client = CruncherClient(
            api_key=settings.anthropic_api_key,
            model=settings.cruncher_model,
            flag_model=settings.cruncher_flag_model,
            baa_in_place=os.getenv("ANTHROPIC_BAA", "false").lower() == "true",
        )
    return _client


# ---------------------------------------------------------------------------
# DB-backed ToolExecutor (has access to database for tool calls)
# ---------------------------------------------------------------------------


class DBToolExecutor(ToolExecutor):
    """Executes Claude tool calls against the real database."""

    def __init__(
        self,
        db: AsyncSession,
        org_id: str,
        current_user: User,
        rag: ClaimRAG,
    ) -> None:
        self.db = db
        self.org_id = org_id
        self.current_user = current_user
        self.rag = rag

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        match tool_name:
            case "get_claim":
                return await self._get_claim(tool_input["claim_id"])
            case "get_claim_lines":
                return await self._get_claim_lines(tool_input["claim_id"])
            case "get_patient_claim_history":
                return await self._get_patient_history(
                    tool_input["patient_id"], tool_input.get("limit", 10)
                )
            case "get_claim_documents":
                return await self._get_claim_documents(tool_input["claim_id"])
            case "flag_claim":
                return await self._flag_claim(
                    tool_input["claim_id"],
                    tool_input["reason"],
                    tool_input.get("priority", 2),
                )
            case "create_ticket":
                return await self._create_ticket(tool_input)
            case "search_similar_claims":
                return await self._search_similar(
                    tool_input["query"], tool_input.get("limit", 5)
                )
            case _:
                return {"error": f"Unknown tool: {tool_name}"}

    async def _get_claim(self, claim_id: str) -> dict[str, Any]:
        result = await self.db.execute(
            select(Claim).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.organization_id == uuid.UUID(self.org_id),
                Claim.deleted_at.is_(None),
            )
        )
        claim = result.scalar_one_or_none()
        if claim is None:
            return {"error": f"Claim {claim_id} not found"}
        return {
            "id": str(claim.id),
            "claim_number": claim.claim_number,
            "form_type": claim.form_type,
            "status": claim.status,
            "date_of_service_from": str(claim.date_of_service_from) if claim.date_of_service_from else None,
            "date_of_service_to": str(claim.date_of_service_to) if claim.date_of_service_to else None,
            "total_charges": float(claim.total_charges) if claim.total_charges else None,
            "total_paid": float(claim.total_paid) if claim.total_paid else None,
            "provider_npi": claim.provider_npi,
            "referring_npi": claim.referring_npi,
            "place_of_service": claim.place_of_service,
            "flagged": claim.flagged,
            "flag_reason": claim.flag_reason,
            "priority": claim.priority,
            "notes": claim.notes,
        }

    async def _get_claim_lines(self, claim_id: str) -> dict[str, Any]:
        # Query claim_lines table (from migration 007)
        rows = await self.db.execute(
            text_query(
                "SELECT cpt_code, icd_code, modifier, description, units, "
                "charge_amount, paid_amount, place_of_service "
                "FROM claim_lines WHERE claim_id = :id ORDER BY line_number",
                {"id": claim_id},
            )
        )
        lines = [dict(row._mapping) for row in rows.fetchall()]
        return {"claim_id": claim_id, "lines": lines, "count": len(lines)}

    async def _get_patient_history(self, patient_id: str, limit: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(Claim)
            .where(
                Claim.patient_id == uuid.UUID(patient_id),
                Claim.organization_id == uuid.UUID(self.org_id),
                Claim.deleted_at.is_(None),
            )
            .order_by(Claim.created_at.desc())
            .limit(min(limit, 20))
        )
        claims = result.scalars().all()
        return {
            "patient_id": patient_id,
            "count": len(claims),
            "claims": [
                {
                    "id": str(c.id),
                    "claim_number": c.claim_number,
                    "status": c.status,
                    "date_of_service_from": str(c.date_of_service_from) if c.date_of_service_from else None,
                    "total_charges": float(c.total_charges) if c.total_charges else None,
                    "flagged": c.flagged,
                }
                for c in claims
            ],
        }

    async def _get_claim_documents(self, claim_id: str) -> dict[str, Any]:
        rows = await self.db.execute(
            text_query(
                "SELECT id, file_name, mime_type, ocr_status, ocr_text, "
                "ocr_confidence, page_count, created_at "
                "FROM claim_documents WHERE claim_id = :id AND deleted_at IS NULL",
                {"id": claim_id},
            )
        )
        docs = []
        for row in rows.fetchall():
            d = dict(row._mapping)
            # Truncate OCR text for tool response
            if d.get("ocr_text") and len(d["ocr_text"]) > 2000:
                d["ocr_text"] = d["ocr_text"][:2000] + "... [truncated]"
            docs.append(d)
        return {"claim_id": claim_id, "documents": docs, "count": len(docs)}

    async def _flag_claim(self, claim_id: str, reason: str, priority: int) -> dict[str, Any]:
        result = await self.db.execute(
            select(Claim).where(
                Claim.id == uuid.UUID(claim_id),
                Claim.organization_id == uuid.UUID(self.org_id),
                Claim.deleted_at.is_(None),
            )
        )
        claim = result.scalar_one_or_none()
        if claim is None:
            return {"error": f"Claim {claim_id} not found"}

        await self.db.execute(
            update(Claim)
            .where(Claim.id == uuid.UUID(claim_id))
            .values(
                flagged=True,
                flag_reason=reason,
                priority=min(max(priority, 0), 5),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()
        return {"flagged": True, "claim_id": claim_id, "reason": reason}

    async def _create_ticket(self, inp: dict[str, Any]) -> dict[str, Any]:
        ticket_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text_query(
                "INSERT INTO tickets (id, organization_id, claim_id, title, description, "
                "ticket_type, status, priority, created_by_id, created_at, updated_at) "
                "VALUES (:id, :org_id, :claim_id, :title, :desc, :type, 'open', :priority, "
                ":created_by, :now, :now)",
                {
                    "id": ticket_id,
                    "org_id": self.org_id,
                    "claim_id": inp.get("claim_id"),
                    "title": inp["title"][:255],
                    "desc": inp.get("description", ""),
                    "type": inp.get("ticket_type", "general"),
                    "priority": inp.get("priority", 2),
                    "created_by": str(self.current_user.id),
                    "now": now,
                },
            )
        )
        await self.db.commit()
        return {"ticket_id": ticket_id, "created": True, "title": inp["title"]}

    async def _search_similar(self, query: str, limit: int) -> dict[str, Any]:
        results = await self.rag.search(query, limit=min(limit, 10))
        return {"query": query, "results": results, "count": len(results)}


def text_query(sql: str, params: dict) -> Any:
    """Wrapper to keep import of sqlalchemy.text local."""
    from sqlalchemy import text
    return text(sql).bindparams(**params)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    claim_id: str | None = None
    include_rag: bool = True


class AnalyzeClaimResponse(BaseModel):
    claim_id: str
    flags: list[dict]
    analysis: str
    tickets_created: int
    model_used: str


class DenialAnalysisRequest(BaseModel):
    denial_reason: str


class DenialAnalysisResponse(BaseModel):
    claim_id: str
    root_cause: str
    disputable: bool | None
    dispute_likelihood: str
    appeal_strategy: str
    appeal_steps: list[str]
    appeal_letter_language: str
    documentation_needed: list[str]
    timely_filing_deadline: str | None


class ParseEOBRequest(BaseModel):
    ocr_text: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/chat")
async def cruncher_chat(
    body: ChatRequest,
    current_user: User = Depends(require_permission("cruncher:chat")),
    db: AsyncSession = Depends(get_db),
):
    """Streaming interactive AI assistant for billers and coders.

    Returns Server-Sent Events (SSE). Each chunk is a text delta.
    Connect with EventSource in the frontend or stream with fetch().

    The assistant has live access to claim data and can flag claims,
    create tickets, and search prior claims — all in real time.

    BAA required when claim_id is provided (claim data sent to Claude API).
    """
    if body.claim_id:
        require_baa()
    client = get_cruncher_client()
    org_id = str(current_user.organization_id) if current_user.organization_id else ""

    rag = ClaimRAG(db=db, org_id=org_id)
    executor = DBToolExecutor(db=db, org_id=org_id, current_user=current_user, rag=rag)

    # Inject claim context if claim_id provided
    context: dict | None = None
    if body.claim_id:
        claim_data = await executor._get_claim(body.claim_id)
        if "error" not in claim_data:
            context = {"current_claim": claim_data}

    # Inject RAG context if requested
    if body.include_rag and org_id:
        rag_context = await rag.get_context_for_chat(body.message, limit=3)
        if rag_context:
            if context is None:
                context = {}
            context["similar_claims_context"] = rag_context

    async def event_stream():
        try:
            async for chunk in client.chat_stream(
                message=body.message,
                context=context,
                tool_executor=executor,
            ):
                # SSE format: data: <chunk>\n\n
                escaped = chunk.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx: disable response buffering
        },
    )


@router.post("/analyze-claim/{claim_id}", response_model=AnalyzeClaimResponse)
async def analyze_claim(
    claim_id: str,
    current_user: User = Depends(require_permission("cruncher:chat")),
    db: AsyncSession = Depends(get_db),
):
    """Full AI analysis of a claim.

    Fetches claim + lines, runs auto-flag scan, returns structured findings.
    Flags and tickets are written to the database in real time.
    BAA required — claim data is sent to Claude API.
    """
    require_baa()
    client = get_cruncher_client()
    org_id = str(current_user.organization_id) if current_user.organization_id else ""
    rag = ClaimRAG(db=db, org_id=org_id)
    executor = DBToolExecutor(db=db, org_id=org_id, current_user=current_user, rag=rag)

    # Fetch claim
    claim_data = await executor._get_claim(claim_id)
    if "error" in claim_data:
        raise HTTPException(status_code=404, detail=claim_data["error"])

    # Fetch documents for OCR text
    docs = await executor._get_claim_documents(claim_id)
    ocr_texts = " ".join(
        d.get("ocr_text", "") or ""
        for d in docs.get("documents", [])
        if d.get("ocr_status") == "completed"
    )

    # Run auto-flag
    flags = await client.auto_flag(
        claim_id=claim_id,
        ocr_text=ocr_texts or "(no OCR text available)",
        structured_data=claim_data,
        tool_executor=executor,
    )

    tickets_created = sum(1 for f in flags if f.get("ticket_created"))

    # Generate brief summary analysis
    flag_summary = (
        f"{len(flags)} issue(s) found" if flags
        else "No issues detected — claim looks clean."
    )

    return AnalyzeClaimResponse(
        claim_id=claim_id,
        flags=flags,
        analysis=flag_summary,
        tickets_created=tickets_created,
        model_used=client.flag_model,
    )


@router.post("/denial-analysis/{claim_id}", response_model=DenialAnalysisResponse)
async def denial_analysis(
    claim_id: str,
    body: DenialAnalysisRequest,
    current_user: User = Depends(require_permission("cruncher:chat")),
    db: AsyncSession = Depends(get_db),
):
    """Analyze a denial and return a full appeal strategy.

    Provide the denial reason from the payer's remittance/EOB.
    Returns root cause, whether it's disputable, exact appeal steps,
    draft appeal letter language, and required documentation.
    BAA required — claim data is sent to Claude API.
    """
    require_baa()
    client = get_cruncher_client()
    org_id = str(current_user.organization_id) if current_user.organization_id else ""
    rag = ClaimRAG(db=db, org_id=org_id)
    executor = DBToolExecutor(db=db, org_id=org_id, current_user=current_user, rag=rag)

    claim_data = await executor._get_claim(claim_id)
    if "error" in claim_data:
        raise HTTPException(status_code=404, detail=claim_data["error"])

    lines_data = await executor._get_claim_lines(claim_id)
    similar = await rag.search(
        f"denial {body.denial_reason} {claim_data.get('form_type', '')}", limit=3
    )

    result = await client.analyze_denial(
        claim_data=claim_data,
        denial_reason=body.denial_reason,
        claim_lines=lines_data.get("lines", []),
        similar_claims=similar,
    )

    return DenialAnalysisResponse(
        claim_id=claim_id,
        root_cause=result.get("root_cause", body.denial_reason),
        disputable=result.get("disputable"),
        dispute_likelihood=result.get("dispute_likelihood", "unknown"),
        appeal_strategy=result.get("appeal_strategy", ""),
        appeal_steps=result.get("appeal_steps", []),
        appeal_letter_language=result.get("appeal_letter_language", ""),
        documentation_needed=result.get("documentation_needed", []),
        timely_filing_deadline=result.get("timely_filing_deadline"),
    )


@router.post("/parse-eob")
async def parse_eob(
    body: ParseEOBRequest,
    current_user: User = Depends(require_permission("cruncher:chat")),
    db: AsyncSession = Depends(get_db),
):
    """Extract structured fields from EOB OCR text.

    Pass in raw OCR text from an Explanation of Benefits.
    Returns a normalized dict with claim numbers, dates, charges, service lines,
    denial codes, and remark codes — ready for DB import.
    """
    client = get_cruncher_client()
    result = await client.parse_eob(body.ocr_text)
    return {"parsed": result, "model_used": client.flag_model}


@router.get("/health")
async def cruncher_health(
    current_user: User = Depends(get_current_user),
):
    """Check if Cruncher AI is configured and reachable."""
    configured = bool(settings.anthropic_api_key)
    return {
        "configured": configured,
        "model": settings.cruncher_model if configured else None,
        "flag_model": settings.cruncher_flag_model if configured else None,
        "baa_in_place": os.getenv("ANTHROPIC_BAA", "false").lower() == "true",
    }
