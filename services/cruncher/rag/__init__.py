"""RAG layer for Claim Cruncher — pgvector similarity search over claim history.

Provides semantic search so Cruncher can find prior claims with similar
procedure codes, denial patterns, or clinical descriptions to ground its
analysis in real precedents from the organization's own claim history.

Requires: pgvector extension (already in 001_organizations.sql)
Model: Uses a simple embedding approach — configurable via EMBEDDING_MODEL env var.
  - "local": TF-IDF style keyword matching (no external API, works offline)
  - "openai": text-embedding-3-small (fast, cheap)
  - "anthropic": not supported for embeddings — falls back to "local"

For Gavin's demo: "local" mode works out of the box with no extra API keys.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Embedding (pluggable)
# ---------------------------------------------------------------------------


async def embed_text(text_input: str, model: str = "local") -> list[float]:
    """Generate a vector embedding for text.

    local: 128-dim keyword frequency vector (works offline, no API key)
    openai: 1536-dim via text-embedding-3-small
    """
    if model == "openai":
        return await _embed_openai(text_input)
    return _embed_local(text_input)


def _embed_local(text_input: str) -> list[float]:
    """128-dim deterministic embedding from keyword frequency.

    Not semantic — but good enough for demo + offline use.
    Upgrade to openai/sentence-transformers for production.
    """
    # Vocabulary: common medical billing terms
    vocab = [
        "cpt", "icd", "npi", "denial", "appeal", "authorization", "modifier",
        "bilateral", "inpatient", "outpatient", "office", "emergency", "surgical",
        "diagnosis", "procedure", "claim", "charge", "payment", "adjustment",
        "timely", "filing", "medical", "necessity", "coordination", "benefits",
        "primary", "secondary", "deductible", "copay", "coinsurance", "network",
        "radiology", "laboratory", "pathology", "anesthesia", "facility", "professional",
        "cms", "ub04", "cms1500", "hcpcs", "revenue", "code", "units", "service",
        "date", "provider", "patient", "insured", "payer", "group", "policy",
        "place", "taxonomy", "rendering", "referring", "ordering", "supervising",
        "duplicate", "bundled", "unbundled", "downcoded", "upcoded", "not covered",
        "excluded", "experimental", "investigational", "cosmetic", "elective",
        "preventive", "wellness", "screening", "diagnostic", "therapeutic",
        "acute", "chronic", "pre-existing", "prior", "concurrent", "subsequent",
        "ambulatory", "home", "hospice", "skilled", "nursing", "rehab", "therapy",
        "physical", "occupational", "speech", "mental", "behavioral", "substance",
        "cardiovascular", "orthopedic", "neurology", "oncology", "obstetric",
        "pediatric", "geriatric", "dermatology", "ophthalmology", "urology",
        "gastro", "pulmonary", "endocrine", "immunology", "infectious", "trauma",
        "wound", "fracture", "sprain", "laceration", "contusion", "burn",
        "injection", "infusion", "administration", "evaluation", "management",
        "consult", "followup", "new", "established", "intraoperative", "postoperative",
        "preoperative", "global", "technical", "interpretation", "supervision",
        "assistant", "team", "cosurgery", "teaching", "hospital", "critical",
    ]
    assert len(vocab) <= 128

    tokens = re.findall(r"\b[a-z0-9]+\b", text_input.lower())
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1

    vec = [float(counts.get(w, 0)) for w in vocab]
    # Pad to 128
    while len(vec) < 128:
        vec.append(0.0)
    # L2 normalize
    norm = (sum(x * x for x in vec) ** 0.5) or 1.0
    return [x / norm for x in vec]


async def _embed_openai(text_input: str) -> list[float]:
    """OpenAI text-embedding-3-small (1536-dim)."""
    try:
        import openai  # type: ignore
        client = openai.AsyncOpenAI()
        resp = await client.embeddings.create(
            input=text_input,
            model="text-embedding-3-small",
        )
        return resp.data[0].embedding
    except Exception:
        # Fallback to local if openai not installed or key missing
        return _embed_local(text_input)


# ---------------------------------------------------------------------------
# pgvector migration helper
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 128  # Match _embed_local output

CREATE_EMBEDDING_TABLE = """
CREATE TABLE IF NOT EXISTS claim_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),
    content_hash    VARCHAR(64) NOT NULL,
    embedding       vector({dim}),
    content_text    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embedding_claim ON claim_embeddings (claim_id);
CREATE INDEX IF NOT EXISTS idx_embedding_org ON claim_embeddings (organization_id);
CREATE INDEX IF NOT EXISTS idx_embedding_vector
    ON claim_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
""".format(dim=EMBEDDING_DIM)


# ---------------------------------------------------------------------------
# ClaimRAG
# ---------------------------------------------------------------------------


class ClaimRAG:
    """Semantic search over org-scoped claim history using pgvector."""

    def __init__(self, db: AsyncSession, org_id: str, model: str = "local") -> None:
        self.db = db
        self.org_id = org_id
        self.embed_model = model

    async def ensure_table(self) -> None:
        """Create claim_embeddings table if it doesn't exist."""
        await self.db.execute(text(CREATE_EMBEDDING_TABLE))
        await self.db.commit()

    async def index_claim(
        self,
        claim_id: str,
        claim_data: dict[str, Any],
        claim_lines: list[dict] | None = None,
    ) -> None:
        """Generate and store an embedding for a claim.

        Content = flattened claim fields + CPT/ICD codes from lines.
        Idempotent — won't re-embed if content hasn't changed.
        """
        content_parts = [
            f"claim_number: {claim_data.get('claim_number', '')}",
            f"status: {claim_data.get('status', '')}",
            f"form_type: {claim_data.get('form_type', '')}",
            f"provider_npi: {claim_data.get('provider_npi', '')}",
            f"place_of_service: {claim_data.get('place_of_service', '')}",
            f"flag_reason: {claim_data.get('flag_reason', '')}",
            f"notes: {claim_data.get('notes', '')}",
        ]
        if claim_lines:
            for line in claim_lines:
                content_parts.append(
                    f"cpt:{line.get('cpt_code', '')} icd:{line.get('icd_code', '')} "
                    f"mod:{line.get('modifier', '')} desc:{line.get('description', '')}"
                )

        content = " ".join(content_parts)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Check if already indexed with same content
        existing = await self.db.execute(
            text(
                "SELECT id FROM claim_embeddings "
                "WHERE claim_id = :claim_id AND content_hash = :hash"
            ),
            {"claim_id": claim_id, "hash": content_hash},
        )
        if existing.scalar_one_or_none():
            return  # Already up to date

        vec = await embed_text(content, self.embed_model)
        vec_str = "[" + ",".join(str(v) for v in vec) + "]"

        await self.db.execute(
            text(
                "INSERT INTO claim_embeddings "
                "(claim_id, organization_id, content_hash, embedding, content_text) "
                "VALUES (:claim_id, :org_id, :hash, :vec::vector, :content) "
                "ON CONFLICT DO NOTHING"
            ),
            {
                "claim_id": claim_id,
                "org_id": self.org_id,
                "hash": content_hash,
                "vec": vec_str,
                "content": content[:4000],
            },
        )
        await self.db.commit()

    async def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find similar claims using cosine similarity.

        Returns list of {"claim_id": str, "similarity": float, "content_text": str}
        """
        try:
            await self.ensure_table()
        except Exception:
            return []

        vec = await embed_text(query, self.embed_model)
        vec_str = "[" + ",".join(str(v) for v in vec) + "]"

        try:
            rows = await self.db.execute(
                text(
                    "SELECT claim_id, content_text, "
                    "1 - (embedding <=> :vec::vector) AS similarity "
                    "FROM claim_embeddings "
                    "WHERE organization_id = :org_id "
                    "ORDER BY embedding <=> :vec::vector "
                    "LIMIT :limit"
                ),
                {"vec": vec_str, "org_id": self.org_id, "limit": limit},
            )
            return [
                {
                    "claim_id": str(row.claim_id),
                    "similarity": float(row.similarity),
                    "content_text": row.content_text,
                }
                for row in rows.fetchall()
            ]
        except Exception:
            return []

    async def get_context_for_chat(self, query: str, limit: int = 3) -> str:
        """Return a formatted context block of similar claims for injection into chat."""
        results = await self.search(query, limit=limit)
        if not results:
            return ""
        lines = ["**Similar claims from your organization's history:**"]
        for r in results:
            sim_pct = int(r["similarity"] * 100)
            lines.append(f"- Claim {r['claim_id'][:8]}... ({sim_pct}% similar): {r['content_text'][:200]}")
        return "\n".join(lines)
