# FDrive API (``)

Backend only — frontend is in `../Fdrive-frontend/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env.example .env

# Requires Postgres (from repo root: docker compose up -d postgres)
alembic upgrade head
uvicorn main:app --reload --port 8000
```

```bash
pytest -q
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
