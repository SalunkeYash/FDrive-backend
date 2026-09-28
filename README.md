# FDrive

Cloud drive SaaS API — FastAPI backend, Postgres metadata, S3-compatible object storage.

Frontend: separate repo at `../Fdrive-frontend`  
Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Testing: [docs/TESTING.md](docs/TESTING.md)

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI · Python 3.11+ |
| DB | PostgreSQL 16 |
| Cache | Redis 7 |
| Objects | MinIO locally → AWS S3 in prod |
| Workers | SQS consumers |

## Repo layout (company backend style)

```
main.py                 App entry
routes/api.py           Router aggregation
auth/ account/ folders/ files/ trash/ shares/ ...
models/                 SQLAlchemy entities
model_handler/          DB access helpers
service/                Business logic
dependencies/           Auth, config, session, response envelope
middleware/             Errors, logging, security headers
integrations/           S3, Redis, SQS
workers/                Background jobs
alembic/ tests/
```

## Quick start

```bash
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health  
- OpenAPI: http://localhost:8000/docs  

API responses: `{ "ok": true, "data": ... }` / `{ "ok": false, "message": ... }`

### Worker (optional)

```bash
source .venv/bin/activate
PYTHONPATH=. python -m workers
```

### Frontend

```bash
cd ../Fdrive-frontend
npm install
npm run dev
```

## Makefile helpers

```bash
make infra-up
make api
make migrate
make test-api
make load-test
```
