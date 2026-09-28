.PHONY: infra-up infra-down infra-logs api install migrate migrate-down test-api load-test

infra-up:
	docker compose up -d

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

api:
	. .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	. .venv/bin/activate && alembic upgrade head

migrate-down:
	. .venv/bin/activate && alembic downgrade -1

test-api:
	. .venv/bin/activate && pytest -q

load-test:
	. .venv/bin/activate && locust -f loadtest/locustfile.py --host http://localhost:8000
