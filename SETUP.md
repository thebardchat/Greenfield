# Claim Cruncher — Quick-Start Guide

> **Wedding gift build** — Shane → Gavin  
> Built with FastAPI · PostgreSQL/pgvector · React/TypeScript · Claude AI  
> Target: Production-ready in 11 days. Current status: **feature complete, needs first deploy.**

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Docker + Docker Compose | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org/) |
| Python | 3.11+ | [python.org](https://www.python.org/) |
| Git | 2.40+ | system package manager |

For OCR (local Tesseract):
```bash
# Ubuntu / Debian
sudo apt-get install tesseract-ocr poppler-utils

# macOS
brew install tesseract poppler
```

---

## 1. Clone and Configure

```bash
git clone https://github.com/thebardchat/Greenfield.git
cd Greenfield

# Copy env template
cp .env.example .env
```

Open `.env` and set **at minimum**:

```bash
# Your Claude API key — get one at console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-api03-...

# Change this before going to production!
JWT_SECRET=some-long-random-string-here
```

Everything else works with the defaults for local development.

---

## 2. Start Infrastructure (Postgres + Redis + MinIO)

```bash
docker-compose up -d postgres redis minio
```

Wait ~10 seconds for Postgres to initialize, then verify:

```bash
docker-compose ps
# Should show postgres, redis, minio as "Up"
```

---

## 3. Run Database Migrations

```bash
# From repo root — runs all SQL files in order
for f in db/migrations/*.sql; do
  echo "Running $f..."
  docker-compose exec -T postgres \
    psql -U claimcruncher -d claimcruncher < "$f"
done
```

Or run them one at a time if you prefer:

```bash
docker-compose exec -T postgres \
  psql -U claimcruncher -d claimcruncher < db/migrations/001_organizations.sql
# ... through 014_claim_embeddings.sql
```

> **Note on migration 014**: requires the `pgvector` extension, which is included
> in the `pgvector/pgvector:pg16` Docker image used in `docker-compose.yml`.
> If you're running a bare Postgres, install the extension manually:
> ```sql
> CREATE EXTENSION IF NOT EXISTS vector;
> ```

---

## 4. Seed the Database

```bash
# Creates: demo org, admin user (admin@claimcruncher.com / Admin1234!),
#          sample payers, credentials, and 10 demo claims
python db/seed.py
```

---

## 5. Start the API

```bash
cd apps/api
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Verify: [http://localhost:8000/api/health](http://localhost:8000/api/health)

```json
{ "status": "ok", "version": "0.1.0", "environment": "development" }
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 6. Start the OCR Worker

Open a new terminal:

```bash
cd apps/worker
pip install -e ".[dev]"
arq app.main.WorkerSettings
```

You should see:
```
Worker started. Redis: redis://localhost:6380/0
```

The worker picks up document processing jobs automatically when files are uploaded.

---

## 7. Start the Frontend

Open another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Frontend: [http://localhost:5173](http://localhost:5173)

Log in with: `admin@claimcruncher.com` / `Admin1234!`

---

## 8. Verify Cruncher AI

```bash
curl -s http://localhost:8000/api/cruncher/health | python -m json.tool
```

Expected response:
```json
{
  "status": "ok",
  "cruncher_enabled": true,
  "model": "claude-sonnet-4-6",
  "flag_model": "claude-haiku-4-5-20251001",
  "rag_enabled": true,
  "baa_in_place": false
}
```

If `cruncher_enabled` is `false`, your `ANTHROPIC_API_KEY` is missing from `.env`.

---

## 9. Test the Full Stack

1. Open [http://localhost:5173](http://localhost:5173)
2. Log in → **Claims** → click any demo claim
3. Click **"Chat about this claim"** — Cruncher AI panel opens
4. Type: *"What CPT codes are billed? Are there any potential issues?"*
5. Watch Claude stream a response with tool call badges (🔧 get_claim, 🔧 get_claim_lines)

For denial analysis:
1. Open a claim with status `denied`
2. Click **"Denial analysis"** → Claude returns dispute likelihood + appeal letter language

---

## Docker Compose (all services at once)

For a full one-command start once you've done steps 1-4 at least once:

```bash
docker-compose up -d
```

Services started:
- `postgres` — port 5433
- `redis` — port 6380
- `minio` — ports 9002 (API), 9003 (console)
- `api` — port 8000
- `worker` — (no port; connects to redis)
- `web` — port 5173

---

## Common Issues

### "pgvector extension not found"
The pgvector extension must be in your Postgres. The Docker image
`pgvector/pgvector:pg16` includes it. If using bare Postgres:
```bash
# Ubuntu
sudo apt-get install postgresql-16-pgvector
```

### "Tesseract not found"
```bash
sudo apt-get install tesseract-ocr   # Linux
brew install tesseract               # macOS
```

### "cruncher_enabled: false"
Your `ANTHROPIC_API_KEY` is empty in `.env`. Get a key at
[console.anthropic.com](https://console.anthropic.com).

### API returns 401 everywhere after login
JWT secret mismatch — make sure `JWT_SECRET` in `.env` matches what
was used when tokens were issued. Delete browser cookies and re-login.

### Worker not picking up jobs
Check Redis is running: `docker-compose ps redis`  
Check REDIS_URL in `.env` matches what the worker connects to (default: `redis://localhost:6380/0`)

---

## Project Structure

```
Greenfield/
├── apps/
│   ├── api/             FastAPI backend (port 8000)
│   │   └── app/
│   │       ├── routers/ REST endpoints
│   │       ├── models/  SQLAlchemy ORM models
│   │       └── main.py  App factory
│   ├── web/             React + Vite frontend (port 5173)
│   │   └── src/
│   │       ├── pages/   Route-level components (Dashboard, Claims, Cruncher...)
│   │       ├── components/ Shared UI
│   │       └── lib/api.ts  Typed API client
│   └── worker/          arq async worker (OCR pipeline)
│       └── app/
│           ├── ocr/     OCR providers (Tesseract + cloud stubs)
│           └── tasks/   Task functions (process_document)
├── services/
│   └── cruncher/        Claude AI integration
│       ├── client.py    CruncherClient (chat, auto-flag, denial, EOB)
│       ├── tools/       Tool schemas for Claude tool use
│       └── rag/         pgvector semantic search
├── db/
│   ├── migrations/      SQL migrations (001 → 014)
│   └── seed.py          Demo data loader
├── docker-compose.yml
├── .env.example
└── SETUP.md             ← you are here
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Claude API key |
| `CRUNCHER_MODEL` | `claude-sonnet-4-6` | Model for chat + denial analysis |
| `CRUNCHER_FLAG_MODEL` | `claude-haiku-4-5-20251001` | Fast model for auto-flagging |
| `ANTHROPIC_BAA` | `false` | Skip PHI de-identification (requires signed BAA) |
| `DATABASE_URL` | local postgres | Async SQLAlchemy URL |
| `REDIS_URL` | local redis | arq job queue |
| `JWT_SECRET` | `change-me` | **Change before prod!** |
| `STORAGE_BACKEND` | `local` | `local` or `s3` (MinIO) |
| `OCR_CONFIDENCE_THRESHOLD` | `0.85` | Tesseract confidence floor before cloud fallback |
| `OCR_CLOUD_PROVIDER` | `none` | `document_ai` or `textract` for cloud OCR |

---

## Production Checklist

- [ ] Set a real `JWT_SECRET` (min 32 random chars)
- [ ] Set `APP_ENV=production`
- [ ] Use HTTPS (nginx reverse proxy + Let's Encrypt)
- [ ] Switch `STORAGE_BACKEND=s3` + configure MinIO or real S3
- [ ] Set `ANTHROPIC_BAA=true` only after signing Anthropic's BAA agreement
- [ ] Configure database backups
- [ ] Set up log aggregation (Grafana Loki, Datadog, etc.)
- [ ] Run `VACUUM ANALYZE claim_embeddings` after initial data load

---

*Built with ❤️ for Gavin — May 2, 2026*
