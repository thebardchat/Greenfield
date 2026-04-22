# CLAUDE.md — Claim Cruncher

> Medical billing intake platform replacing manual PDF hand-keying.
> Built by Shane Brazelton + Gavin Brazelton + Claude Anthropic
> Stack: Python 3.11+ / FastAPI / PostgreSQL / Redis / arq workers
> Updated: 2026-04-11 | Session 1: Scaffold + schema

## Project Overview

**Claim Cruncher** is an intelligent medical billing intake portal for Gavin's billing company. It replaces a manual workflow where billers hand-key data from PDFs into billing software.

**Six modules:**
1. **Client Submission Portal** — PDF upload, auto-OCR, claim creation
2. **OCR Pipeline** — Tesseract local-first, Google Document AI / AWS Textract fallback
3. **Facility Assignment Manager** — biller/coder mapping per facility
4. **Ticket Queue** — work items for billers/coders with priority + status
5. **Credentialing Portal** — physician NPI, license, DEA expiry tracking + alerts
6. **Client Reporting** — claim summaries, productivity metrics, CSV/txt export

**AI Layer — "Cruncher":**
- Claude API (Messages + tool use) for claim Q&A, issue flagging, denial analysis
- RAG via pgvector over claim history
- Haiku for bulk auto-flagging, Sonnet/Opus for interactive coder chat
- De-identify PHI before sending to Claude API (unless Anthropic BAA in place)

## Architecture

```
claim-cruncher/
├── apps/api/          # FastAPI backend (routers, models, schemas, services, middleware)
├── apps/worker/       # arq background jobs (OCR, alerts, reports)
├── apps/web/          # Frontend (React/Vite — future)
├── db/migrations/     # 13 numbered SQL migration files (stack-agnostic)
├── db/seeds/          # Fake dev data
├── packages/shared/   # Shared enums, constants (claim_status.py, roles.py)
├── services/cruncher/ # Claude API integration (prompts, RAG, tools)
├── uploads/           # Local file storage (gitignored)
├── infra/             # nginx, ssl configs
└── docker-compose.yml # Postgres (pgvector), Redis, MinIO
```

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Migrations | Alembic (wraps db/migrations/) |
| Queue | arq + Redis |
| OCR | pytesseract + pdf2image (local), Document AI / Textract (cloud) |
| AI | Anthropic Claude API (anthropic SDK) |
| Auth | JWT (python-jose + passlib) |
| Storage | Local filesystem → MinIO/S3 migration path |
| Frontend | React + Vite (future) |

## Database Schema (13 tables)

| Table | Purpose |
|-------|---------|
| organizations | Billing company clients |
| users | Billers, coders, admins, clients (role-based) |
| facilities | Hospitals, clinics per org |
| facility_assignments | Biller/coder mapping per facility |
| patients | PHI: name, DOB, MRN, insurance |
| claims | Core entity — status lifecycle, CPT/ICD, assignees |
| claim_lines | CPT/ICD codes per claim line |
| claim_documents | Uploaded PDFs, OCR results, confidence scores |
| tickets | Work queue items linked to claims |
| ticket_comments | Threaded comments (internal vs client-visible) |
| credentials | Physician NPI, license, DEA, board cert |
| credential_alerts | Expiry notifications (30/60/90 day) |
| audit_log | HIPAA append-only log (every PHI read/write) |

### Claim Status Lifecycle
```
submitted → ocr_processing → ready_for_review → in_progress → coded → billed → paid
                │                                                        │
                → ocr_failed                                             → denied → appealed
```

## HIPAA Compliance

This platform handles Protected Health Information (PHI). Every session must respect:

- **Audit everything:** Every PHI access (reads AND writes) logged to audit_log
- **RBAC enforced:** Check user role + org scope on every endpoint
- **Soft deletes only:** Never hard-delete PHI tables (deleted_at column)
- **Encrypt at rest:** pgcrypto for sensitive columns, encrypted filesystem for uploads
- **TLS everywhere:** API, database, Redis, file storage connections
- **De-identify for AI:** Strip names, SSN, insurance IDs before sending to Claude API
- **No PHI in logs:** Application logs must never contain patient data
- **6-year retention:** Audit logs retained minimum 6 years

## Development

### Prerequisites
- Python 3.11+
- Docker + Docker Compose (for Postgres, Redis, MinIO)
- Tesseract OCR: `sudo apt install tesseract-ocr`
- poppler-utils: `sudo apt install poppler-utils` (for pdf2image)

### Setup
```bash
cd claim-cruncher
cp .env.example .env
docker compose up -d                    # Postgres, Redis, MinIO
cd apps/api
pip install -e ".[dev]"                 # Install API dependencies
# Run migrations (once Alembic is configured):
# alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Worker
```bash
cd apps/worker
pip install -e .
arq app.main.WorkerSettings
```

### API Endpoints
All under `/api/`:
- `POST /auth/login` — JWT auth
- `GET|POST /organizations/` — org CRUD
- `GET|POST /facilities/` — facility CRUD + assignment management
- `GET|POST /patients/` — patient CRUD
- `GET|POST /claims/` — claim CRUD + status transitions
- `POST /documents/upload` — PDF upload → OCR queue
- `GET|POST /tickets/` — work queue
- `GET|POST /credentials/` — credential tracking
- `GET /reports/` — summaries, exports
- `POST /cruncher/chat` — AI assistant
- `GET /health` — service health check

## OCR Pipeline Strategy

**Hybrid tiered approach:**
1. **Phase 1 (MVP):** Tesseract local with CMS-1500 template overlay (field-position cropping)
2. **Phase 2:** Google Document AI fallback when confidence < 0.85 (~$0.07-0.10/page)
3. **Phase 3:** Custom Document AI extractor trained on labeled forms

Pipeline: PDF → Tesseract → confidence check → accept (≥0.85) or cloud fallback (<0.85)

OCR providers implement `OcrProvider` ABC in `apps/worker/app/ocr/base.py`.

## Roles & Permissions

| Role | Access |
|------|--------|
| super_admin | Everything |
| org_admin | Full org access (claims, patients, facilities, users, reports) |
| biller | Claims, patients (read), tickets, documents, reports, Cruncher |
| coder | Claims, patients (read), tickets, Cruncher |
| client | Own claims (read), document upload, tickets, reports |
| auditor | Read-only across all resources |

Permission system at `packages/shared/roles.py`.

## Conventions

- **Python style:** ruff for linting, 100-char line length, type hints everywhere
- **API responses:** Pydantic schemas for all request/response models
- **UUIDs:** v7 (time-ordered) for all primary keys
- **Timestamps:** Always TIMESTAMPTZ (UTC)
- **Soft deletes:** `deleted_at` column, app queries filter `WHERE deleted_at IS NULL`
- **Audit trail:** Middleware auto-logs every mutating request + PHI reads
- **File paths:** Never expose upload paths directly — serve through API with RBAC
- **Secrets:** Never in code. `.env` file, gitignored. Vault for production.

## Builders

Shane Brazelton — architecture, infrastructure, AI integration
Gavin Brazelton — domain expertise, billing workflow, client requirements
Claude Anthropic — co-architect, implementation partner

## Implementation Roadmap

| Session | Goal |
|---------|------|
| 1 | Scaffold + schema (DONE) |
| 2 | Docker compose up, run migrations, seed dev data |
| 3 | Auth + RBAC + audit middleware |
| 4 | Document upload + local OCR pipeline |
| 5 | Claims CRUD + status lifecycle |
| 6 | Facility assignments + ticket queue |
| 7 | Credentialing portal + expiry alerts |
| 8 | Cruncher AI integration |
| 9 | Client reporting + export |
| 10 | UI (portal + dashboard) |
