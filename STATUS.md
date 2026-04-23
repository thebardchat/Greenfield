# Claim Cruncher — Status
> Updated: 2026-04-23 | Session 2 audit + implementation

## Module Status

| Module | Status | Notes |
|--------|--------|-------|
| **Auth & RBAC** | Complete | JWT (HS256), argon2 passwords, 6 roles, permission matrix |
| **Claims CRUD** | Complete | Full lifecycle, status transitions, org-scoped, priority/flag |
| **Patients** | Complete | PHI model, org-scoped, soft deletes |
| **Facilities** | Complete | CRUD, org-scoped, assignment endpoints |
| **Organizations** | Complete | CRUD, super-admin scoped |
| **Tickets** | Complete | Work queue, priority, status, threaded comments |
| **Credentials** | Complete | NPI/license/DEA/board cert tracking, expiry endpoint |
| **Documents** | Complete | Upload, download, OCR status polling, local + S3 backends |
| **Reports** | Complete | claims summary, productivity, denial trends, credentials status, CSV export |
| **Audit Middleware** | Complete | HIPAA-compliant, fire-and-forget, every PHI route logged |
| **RBAC Middleware** | Complete | Dependency injection, org isolation enforced |
| **Database Schema** | Complete | 14 tables via SQL migrations (13 core + pgvector embeddings) |
| **Docker Compose** | Complete | Postgres 16 + pgvector, Redis, MinIO |
| **Shared Packages** | Complete | ClaimStatus enum, VALID_TRANSITIONS, UserRole, has_permission |
| **OCR Pipeline (Tesseract)** | Complete | 300 DPI, per-page confidence, verified 0.933 on test PDF |
| **Worker: credential_expiry** | **Implemented** | 90/60/30-day milestones, idempotent, daily cron 07:00 UTC |
| **Worker: report_generation** | **Implemented** | 4 report types (claims, productivity, denial trends, credentials), CSV output |
| **Worker: shared DB session** | **Implemented** | `tasks/_db.py` — single engine pool shared across all 3 tasks |
| **BAA Safety Check** | Complete | `apps/api/app/safety/baa_check.py` — all Cruncher routes gated, 403 if unset |
| **Cruncher AI (chat)** | Complete | Streaming SSE, agentic tool use, RAG context injection |
| **Cruncher AI (auto-flag)** | Complete | Haiku model, structured JSON flags |
| **Cruncher AI (denial analysis)** | Complete | Sonnet model, full appeal strategy |
| **Cruncher AI (EOB parsing)** | Complete | Haiku, structured field extraction from OCR text |
| **Cruncher Tools** | Complete | 7 tools: get_claim, flag_claim, create_ticket, search_similar, etc. |
| **RAG (pgvector)** | Complete | ClaimRAG: local TF-IDF embeddings, semantic search, context formatting |
| **OCR Cloud (Document AI)** | Stub | Cloud fallback not wired — needs GCP credentials |
| **OCR Cloud (Textract)** | Stub | Cloud fallback not wired — needs AWS credentials |
| **Alembic** | Not started | Migrations are raw SQL (014 files) — no Alembic ORM wiring yet |
| **Frontend (React/Vite)** | Not started | `apps/web/` scaffold only |

## API Routes (47 total)

| Router | Endpoints |
|--------|-----------|
| auth | login, me, refresh, register |
| claims | list, create, get, update, transition |
| credentials | list, create, get, update, expiring |
| cruncher | chat (SSE), analyze-claim, denial-analysis, parse-eob, health |
| documents | upload, get, download, ocr-results, delete |
| facilities | list, create, get, update |
| organizations | list, create, get, update, delete |
| patients | list, create, get, update |
| reports | claims-summary, productivity, denial-trends, credentials-status, export |
| tickets | list, create, get, update |

## Worker Tasks

| Task | Trigger | Description |
|------|---------|-------------|
| `process_document` | Per upload (arq enqueue) | OCR → DB → claim advance → RAG → auto-flag |
| `check_credential_expiry` | Daily cron 07:00 UTC | 90/60/30-day alert creation, status updates |
| `generate_report` | On-demand (arq enqueue) | CSV export: claims, productivity, denial trends, credentials |

## Security / HIPAA

- BAA gate on all Cruncher routes transmitting claim data (403 if `BAA_SIGNED=false`)
- HIPAA audit log on every request (append-only, fire-and-forget)
- Soft deletes only — no hard deletes on PHI tables
- Org isolation on every claim/patient/document query
- JWT 15-min access / 7-day refresh tokens
- argon2id password hashing
- PHI de-identification in CruncherClient when `ANTHROPIC_BAA=false`

## Next Priorities

1. Alembic integration — wire 14 SQL migrations into `alembic env.py`
2. Cloud OCR fallback — Document AI (GCP) or Textract (AWS)
3. Frontend — React portal for document upload + biller dashboard
4. E2E test suite — pytest + httpx TestClient against real Postgres
