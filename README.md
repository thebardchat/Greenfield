# Claim Cruncher

> Medical billing intake platform — replacing manual PDF hand-keying with intelligent OCR, AI-assisted coding, and HIPAA-compliant workflow automation.

Built by **Shane Brazelton + Gavin Brazelton + [Claude Anthropic](https://claude.ai/referral/4fAMYN9Ing)**

GitHub org: [https://github.com/thebardchat](https://github.com/thebardchat)

---

## !! HIPAA / BAA WARNING !!

**This platform handles Protected Health Information (PHI).**

The embedded AI assistant (Cruncher) uses the Anthropic Claude API. A signed **Business Associate Agreement (BAA) with Anthropic is required** before sending any patient or claim data to the API.

- All Cruncher routes that transmit claim data will return `403 Forbidden` until `BAA_SIGNED=true` is set in your environment.
- Execute the BAA at [console.anthropic.com](https://console.anthropic.com) before enabling.
- Keep the signed BAA on file for a minimum of 6 years (HIPAA requirement).

---

## Module Status

| Module | Status |
|--------|--------|
| Auth & RBAC | Complete |
| Claims CRUD + lifecycle | Complete |
| Patients | Complete |
| Facilities | Complete |
| Credentials (NPI/license/DEA) | Complete |
| Ticket Queue | Complete |
| HIPAA Audit Middleware | Complete |
| Database schema (13 tables, pgvector) | Complete |
| Docker Compose (Postgres, Redis, MinIO) | Complete |
| OCR Pipeline (Tesseract local) | **Working** — 0.938 confidence on test PDF |
| BAA Safety Gate | **Added** |
| Cruncher AI (chat, auto-flag, denial analysis) | **Working** |
| Documents router (upload/download) | Stub |
| Organizations router | Stub |
| Reports / CSV export | Stub |
| Cloud OCR (Document AI / Textract) | Stub |
| Frontend (React/Vite) | Not started |

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Queue | arq + Redis |
| Storage | Local filesystem → MinIO/S3 |
| OCR | Tesseract (local) + Document AI / Textract (cloud fallback) |
| AI | Anthropic Claude API (Sonnet for chat, Haiku for bulk flagging) |
| Auth | JWT HS256 (python-jose) + argon2 password hashing |

---

## Setup

### Prerequisites

```bash
# System dependencies
sudo apt install tesseract-ocr poppler-utils

# Docker + Docker Compose
docker compose up -d   # starts Postgres (pgvector), Redis, MinIO
```

### API

```bash
cd apps/api
cp ../../.env.example ../../.env
# Edit .env — set ANTHROPIC_API_KEY, JWT_SECRET, etc.

pip install -e ".[dev]"

# Run migrations (raw SQL — Alembic config coming soon)
# Connect to Postgres and run db/migrations/001_*.sql through 013_*.sql in order

uvicorn app.main:app --reload --port 8000
# API docs at http://localhost:8000/docs (development mode only)
```

### Worker (OCR + background jobs)

```bash
cd apps/worker
pip install -e .
arq app.main.WorkerSettings
```

### Environment Variables (key ones)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async URL | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection | `redis://localhost:6380/0` |
| `ANTHROPIC_API_KEY` | Claude API key | *(required for Cruncher)* |
| `JWT_SECRET` | JWT signing secret | **change in production** |
| `BAA_SIGNED` | Enable PHI → Claude API | `false` — **requires BAA** |
| `OCR_CONFIDENCE_THRESHOLD` | Below this → cloud fallback | `0.85` |
| `OCR_CLOUD_PROVIDER` | `none` / `document_ai` / `textract` | `none` |

See `.env.example` for the full list.

---

## Architecture

```
claim-cruncher/
├── apps/api/          # FastAPI backend
├── apps/worker/       # arq background jobs (OCR, alerts, reports)
├── apps/web/          # Frontend (React/Vite — future)
├── db/migrations/     # 13 SQL migration files
├── db/seeds/          # Fake dev data
├── packages/shared/   # Shared enums (ClaimStatus, UserRole)
├── services/cruncher/ # Claude API integration
├── tests/             # OCR pipeline tests (synthetic data only, no PHI)
└── docker-compose.yml # Postgres, Redis, MinIO
```

### Claim Status Lifecycle

```
submitted → ocr_processing → ready_for_review → in_progress → coded → billed → paid
                │                                                       │
                → ocr_failed                                            → denied → appealed
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | JWT login |
| POST | `/api/auth/refresh` | Refresh token |
| POST | `/api/auth/register` | Create user (admin only) |
| GET | `/api/auth/me` | Current user profile |
| GET/POST | `/api/claims/` | List / create claims |
| GET/PATCH | `/api/claims/{id}` | Get / update claim |
| POST | `/api/claims/{id}/transition` | Status transition |
| POST | `/api/documents/upload` | Upload PDF → OCR queue |
| POST | `/api/cruncher/chat` | AI assistant chat |
| POST | `/api/cruncher/analyze-claim/{id}` | Auto-flag issues (BAA required) |
| POST | `/api/cruncher/denial-analysis/{id}` | Appeal strategy (BAA required) |
| GET | `/health` | Service health |

---

## HIPAA Compliance

- Every PHI access logged to `audit_log` (append-only, 6-year retention)
- RBAC enforced on every endpoint — users only see their own org's data
- Soft deletes only — no hard deletes of PHI tables
- No PHI in application logs
- BAA required before any data reaches external AI

---

## Running Tests

```bash
# OCR pipeline smoke test (synthetic data — no real PHI)
python tests/test_ocr_pipeline.py
```

---

*Built with [Claude Code](https://claude.ai/referral/4fAMYN9Ing)*
