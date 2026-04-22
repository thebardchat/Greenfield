-- Migration 014: claim_embeddings (pgvector RAG store)
--
-- Requires: PostgreSQL 15+ with pgvector extension
-- Install: CREATE EXTENSION IF NOT EXISTS vector;
--
-- This table stores dense vector representations of claims for semantic
-- similarity search (Cruncher AI "find similar claims" tool).
--
-- Embedding model: 128-dim local keyword-frequency (offline, no API key)
--                  or text-embedding-ada-002 (OpenAI, if configured)
--
-- The ivfflat index enables approximate nearest-neighbor search.
-- Tuning note: lists = sqrt(row_count) is a reasonable starting point.
-- Re-run VACUUM ANALYZE claim_embeddings after bulk loads.

-- ─────────────────────────────────────────────────────────────────────
-- 1. Enable pgvector extension (idempotent)
-- ─────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────
-- 2. claim_embeddings table
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS claim_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to claims (cascade delete keeps the store in sync)
    claim_id        UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,

    -- Denormalized summary fields — used in search result display
    -- without needing a JOIN back to claims
    patient_id      UUID,
    payer_name      TEXT,
    status          TEXT,
    total_charge    NUMERIC(12, 2),
    denial_reason   TEXT,
    cpt_codes       TEXT[],             -- top-level codes for filtering

    -- The raw text that was embedded (truncated to 4096 chars)
    content_text    TEXT NOT NULL,

    -- Embedding vector (128 dimensions for local model, 1536 for ada-002)
    -- Declared as 128 here; change to vector(1536) if switching to OpenAI
    embedding       vector(128) NOT NULL,

    -- Which model produced this embedding
    embedding_model TEXT NOT NULL DEFAULT 'local-128',

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One embedding per claim (upsert on claim_id)
    CONSTRAINT claim_embeddings_claim_id_unique UNIQUE (claim_id)
);

-- ─────────────────────────────────────────────────────────────────────
-- 3. ivfflat index for cosine similarity ANN search
--
-- lists=100 is reasonable up to ~1M rows.
-- Queries use: ORDER BY embedding <=> query_vec LIMIT k
-- ─────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS claim_embeddings_ivfflat_idx
    ON claim_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ─────────────────────────────────────────────────────────────────────
-- 4. Supporting indexes
-- ─────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS claim_embeddings_claim_id_idx
    ON claim_embeddings (claim_id);

CREATE INDEX IF NOT EXISTS claim_embeddings_payer_idx
    ON claim_embeddings (payer_name)
    WHERE payer_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS claim_embeddings_status_idx
    ON claim_embeddings (status)
    WHERE status IS NOT NULL;

CREATE INDEX IF NOT EXISTS claim_embeddings_cpt_codes_idx
    ON claim_embeddings USING GIN (cpt_codes);

-- ─────────────────────────────────────────────────────────────────────
-- 5. updated_at trigger (keeps updated_at current on upsert)
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_claim_embeddings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS claim_embeddings_updated_at_trigger ON claim_embeddings;

CREATE TRIGGER claim_embeddings_updated_at_trigger
    BEFORE UPDATE ON claim_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_claim_embeddings_updated_at();

-- ─────────────────────────────────────────────────────────────────────
-- 6. Comments
-- ─────────────────────────────────────────────────────────────────────
COMMENT ON TABLE claim_embeddings IS
    'Dense vector store for Cruncher AI semantic claim similarity search. '
    'Populated by ClaimRAG.index_claim() after OCR pipeline completion.';

COMMENT ON COLUMN claim_embeddings.embedding IS
    '128-dim L2-normalized keyword-frequency vector (offline default). '
    'Change vector(128) → vector(1536) and embedding_model to use OpenAI ada-002.';

COMMENT ON COLUMN claim_embeddings.content_text IS
    'The text that was vectorized: claim summary + CPT codes + denial reason. '
    'Used for debugging; not returned to users.';
