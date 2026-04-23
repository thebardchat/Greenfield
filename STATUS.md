# Claim Cruncher — Status Audit
> Generated: 2026-04-23 | Session 2 audit

## Module Status

| Module | Status | Notes |
|--------|--------|-------|
| **Auth & RBAC** | Complete | JWT (HS256), argon2 password hashing, 6 roles, permission matrix |
| **Claims CRUD** | Complete | Full lifecycle, status transitions validated, org-scoped |
| **Patients** | Complete | PHI model, org-scoped, soft deletes |
| **Facilities** | Complete | CRUD, org-scoped |
| **Credentials** | Complete | NPI/license/DEA expiry tracking, alert creation |
| **Tickets** | Complete | Work queue, priority, status, threaded comments |
| **Audit Middleware** | Complete | HIPAA-compliant, fire-and-forget, every PHI route |
| **RBAC Middleware** | Complete | Dependency injection pattern, org isolation |
| **Database Schema** | Complete | 13 tables via SQL migrations, pgvector extension |
| **Docker Compose** | Complete | Postgres 16 + pgvector, Redis, MinIO |
| **Shared Packages** | Complete | ClaimStatus enum, VALID_TRANSITIONS, UserRole, has_permission |
| **OCR Pipeline (Tesseract)** | **Fixed this session** | Implemented TesseractProvider; 0.938 confidence on test PDF |
| **Worker DB Setup** | **Fixed this session** | arq startup/shutdown now initializes async SQLAlchemy pool |
| **BAA Safety Check** | **Added this session** | `/api/safety/baa_check.py`; all Cruncher routes gated |
| **Cruncher Router** | **Fixed this session** | chat, analyze-claim, denial-analysis wired with BAA gate |
| **Cruncher AI Client** | **Fixed this session** | Full Claude API implementation: chat, auto_flag, analyze_denial |
| **Cruncher System Prompt** | **Updated this session** | Precise, claim-ID-citing, no PHI in responses |
| **Documents Router** | Stub | upload, download, OCR results endpoints not implemented |
| **Organizations Router** | Stub | CRUD not implemented |
| **Reports Router** | Stub | CSV/txt export not implemented |
| **Worker: credential_expiry** | Stub | 30/60/90 day scan not implemented |
| **Worker: report_generation** | Stub | Export generation not implemented |
| **Cloud OCR (Document AI)** | Stub | Fallback provider not implemented |
| **Cloud OCR (Textract)** | Stub | Fallback provider not implemented |
| **Frontend (React/Vite)** | Not Started | apps/web/ scaffold only |
| **Alembic Config** | Not Started | pyproject.toml lists alembic but no alembic.ini or env.py |
| **pgvector RAG** | Not Started | services/cruncher/rag/ empty |

## Broken Imports / Config Gaps

| Item | Status |
|------|--------|
| `sys.path.insert` for shared packages | Works but fragile — consider pip install -e packages/shared |
| `sys.path.insert` for cruncher service in router | Works but fragile |
| Worker: `RedisSettings()` with no args | Fixed → `RedisSettings.from_dsn(REDIS_URL)` |
| No `.env` file in git | Correct — `.env.example` is tracked, `.env` is gitignored |
| `BAA_SIGNED` missing from config | Fixed — added to Settings with `baa_signed: bool = False` |

## Missing Dependencies

| Package | Location | Status |
|---------|----------|--------|
| `tesseract-ocr` (system) | worker | Installed this session |
| `pytesseract` | worker | Installed this session |
| `pdf2image` | worker | Installed this session |
| `Pillow` | worker | Installed this session |
| `fpdf2` | tests only | Installed this session |
| `poppler-utils` (system) | worker | Already present |

## Security / HIPAA Findings

- **BAA gate added** — all 3 Cruncher routes now call `require_baa()` before touching claim data
- **PHI never logged** — audit middleware logs resource type only, not payload
- **Soft deletes enforced** — all queries filter `deleted_at IS NULL`
- **Org isolation** — all claim/patient queries scoped to `current_user.organization_id`
- **JWT short-lived** — 15-minute access tokens, 7-day refresh tokens

## Next Sessions (Suggested Priority)

1. **Documents router** — PDF upload, checksum, enqueue OCR job
2. **Organizations router** — CRUD
3. **Alembic setup** — wire migrations into Alembic for `alembic upgrade head`
4. **Worker: credential_expiry** — 30/60/90 day scan + Discord/email alert
5. **Reports router** — CSV export for billing software
6. **Cloud OCR providers** — DocumentAI and Textract fallbacks
7. **RAG** — pgvector over claim history for Cruncher context
8. **Frontend** — React portal for claim submission and biller dashboard
