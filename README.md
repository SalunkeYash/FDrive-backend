# FDrive

Personal cloud drive — Vite + React frontend, FastAPI backend, Postgres metadata, S3 object storage.

Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Stack

| Layer | Tech |
|-------|------|
| Web | Vite · React · TypeScript · Tailwind |
| API | FastAPI · Python 3.11+ |
| DB | PostgreSQL 16 |
| Cache | Redis 7 |
| Objects | MinIO locally → AWS S3 in prod |

## Repo layout

```
apps/web/       Vite SPA
apps/api/       FastAPI application
workers/        SQS consumers (Phase 12)
infra/          IaC (Phase 18)
docs/           Architecture & design notes
docker-compose.yml
```

## Prerequisites

- Node.js 20+
- Python 3.11+
- Docker + Docker Compose

## Quick start

### 1. Infrastructure

```bash
docker compose up -d
```

Starts Postgres (`:5432`), Redis (`:6379`), MinIO (`:9000`, console `:9001`). Default bucket: `fdrive`.

### 2. API

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health  
- Ready (DB check): http://localhost:8000/ready  
- OpenAPI: http://localhost:8000/docs  

Frontend lives in `apps/web/` — keep backend (`apps/api/`) and frontend separate.

### 3. Web

```bash
cd apps/web
npm install
npm run dev
```

App: http://localhost:5173 — Vite proxies `/health`, `/ready`, and `/api` to the API.

## Phase status

| Phase | Status |
|-------|--------|
| 01 Project Foundation | Done |
| 02 Database + Data Model | Done |
| 03 Authentication | Done |
| 04 User + Storage Quota | Done |
| 05 Folders | Done |
| 06 File Upload → S3 | Done |
| 07 Download | Done |
| 08 File Management | Done |
| 09 Trash + Restore | Done |
| 10 Sharing + Permissions | Done |
| 11 Search | Done |
| 12 Background Workers + SQS | Next |

## Makefile helpers

```bash
make infra-up      # docker compose up -d
make infra-down    # docker compose down
make api           # run API with reload
make web           # run Vite dev server
```
