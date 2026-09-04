# FDrive testing

## Unit / API tests

From `apps/api` with Postgres running:

```bash
docker compose up -d postgres
cd apps/api && source .venv/bin/activate
alembic upgrade head
pytest -q
```

Or from repo root:

```bash
make test-api
```

## Frontend build check

```bash
make test-web
```

## Load testing

Locust scenarios live in `apps/api/loadtest/`. They exercise auth + profile + folder list against a running API.

```bash
# terminal 1 — API + infra
docker compose up -d
make migrate
make api

# terminal 2 — load test (install locust first)
cd apps/api && source .venv/bin/activate
pip install 'locust>=2.32.0'
locust -f loadtest/locustfile.py --host http://localhost:8000
```

Open http://localhost:8089, start with a small user count (e.g. 10 users, spawn 2/s), and watch p95 latency for `/api/v1/account/profile` and folder listing.

Headless example:

```bash
locust -f loadtest/locustfile.py --host http://localhost:8000 \
  --users 20 --spawn-rate 5 --run-time 1m --headless
```

### What “good” looks like locally

| Endpoint | Target p95 (local) |
|----------|--------------------|
| `POST /auth/login` | < 500 ms |
| `GET /account/profile` | < 100 ms |
| `GET /folders/list-folder-contents` | < 150 ms |

Cloud targets belong in Phase 18/23 once infrastructure is sized.
