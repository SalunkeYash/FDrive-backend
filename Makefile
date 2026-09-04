.PHONY: infra-up infra-down infra-logs api web install migrate migrate-down test-api test-web load-test

infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

install:
	cd apps/api && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd apps/web && npm install

api:
	cd apps/api && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && npm run dev

migrate:
	cd apps/api && . .venv/bin/activate && alembic upgrade head

migrate-down:
	cd apps/api && . .venv/bin/activate && alembic downgrade -1

test-api:
	cd apps/api && . .venv/bin/activate && pytest -q

test-web:
	cd apps/web && npm run build

load-test:
	cd apps/api && . .venv/bin/activate && locust -f loadtest/locustfile.py --host http://localhost:8000
