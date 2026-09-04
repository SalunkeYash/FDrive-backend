# FDrive — System Architecture

> Status: **Foundation** (Phase 01)  
> Scope: architecture and decisions only — no implementation yet.

FDrive is a personal/cloud drive product: users upload files to object storage, organize them in folders, share with permissions, search, preview, and manage quota — with background processing for heavy work.

---

## 1. Goals

| Goal | Implication |
|------|-------------|
| Reliable file storage | S3 is source of truth for bytes; Postgres is source of truth for metadata |
| Fast UX for browse / upload / download | Presigned S3 URLs; Redis for hot metadata & rate limits |
| Safe sharing | Explicit permission model; no public-by-default |
| Scale path | Stateless API + SQS workers; horizontal scale later (Phase 23) |
| Ship incrementally | Phases 01–22 map cleanly onto this architecture |

### Non-goals (for now)

- Multi-region active-active
- Client-side E2E encryption
- Native mobile apps (API-first so they can come later)
- GraphQL (REST first; revisit if needed)

---

## 2. Locked tech decisions

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Frontend | **Vite + React + TypeScript + Tailwind** | Authenticated app shell; Vite is the fit. **Not Next.js** unless we later need SSR/SEO landing pages |
| Backend | **Python + FastAPI** | Fast, typed, good async for I/O-bound APIs |
| API style | **REST** under `/api/v1` | Simple clients; OpenAPI from FastAPI |
| Database | **PostgreSQL** | Relational metadata, constraints, transactions |
| ORM | **SQLAlchemy 2.x** (+ Alembic migrations) | Explicit models, mature Postgres support |
| Object storage | **AWS S3** | Durable blobs; lifecycle + versioning available |
| Cache / ephemeral | **Redis** | Quota counters, sessions/rate limits, job locks |
| Async work | **SQS + Python workers** | Decouple thumbnails, virus scan hooks, indexing |
| Cloud | **AWS** | S3/SQS/ALB/ECS (or similar) in Phase 18 |

### Deferred (decide when the phase starts)

| Topic | Candidates | Decide by |
|-------|------------|-----------|
| Auth provider | Self-hosted JWT vs Cognito / Auth0 | Phase 03 |
| Search engine | Postgres `tsvector` first vs OpenSearch later | Phase 11 |
| Preview stack | LibreOffice / ImageMagick / custom | Phase 13 |
| Billing | Stripe | Phase 21 |
| API gateway | ALB only vs API Gateway + WAF | Phase 15 / 18 |
| Monolith vs services | Modular monolith until scaling forces a split | Phase 23 |

---

## 3. High-level system view

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (Vite + React SPA)                                     │
│  Auth UI · File browser · Upload · Share · Search · Preview     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (REST /api/v1)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Edge: DNS → TLS → ALB (+ WAF later)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────────┐   ┌─────────────────────────┐
│  FastAPI (API service)  │   │  Workers (Python)       │
│  Auth · Files · Folders │   │  Thumbnails · Indexing  │
│  Shares · Quota · Search│   │  Preview · Cleanup      │
└───────────┬─────────────┘   └───────────┬─────────────┘
            │                             │
     ┌──────┼──────────┬──────────────────┼──────┐
     ▼      ▼          ▼                  ▼      ▼
 Postgres  Redis      S3               SQS    (S3 events
 metadata  cache   object bytes      job     optional)
           locks   presigned I/O     queue
```

**Rule of thumb:** the API never streams large file bodies through the app server in steady state. Clients talk to S3 via **presigned URLs**; the API only authorizes and records metadata.

---

## 4. Repository layout (target)

```
FDrive/
├── apps/
│   ├── web/                 # Vite + React + Tailwind
│   └── api/                 # FastAPI application
├── workers/                 # SQS consumers (same Python package deps as API)
├── packages/                # Optional shared TS types later
├── infra/                   # IaC (Phase 18) — Terraform or CDK
├── docs/
│   └── ARCHITECTURE.md      # this file
└── docker-compose.yml       # local Postgres, Redis, LocalStack/MinIO, API, worker
```

Monorepo keeps API + workers sharing domain models and DB access. Split deployables without splitting the repo early.

---

## 5. Backend architecture (modular monolith)

```
apps/api/
├── main.py                  # app factory, middleware, routers
├── core/                    # config, security, logging, deps
├── db/                      # engine, session, base
├── models/                  # SQLAlchemy models
├── schemas/                 # Pydantic request/response
├── routers/                 # HTTP adapters (thin)
├── services/                # business logic
├── integrations/            # S3, Redis, SQS, email later
└── workers/ hooks           # enqueue helpers (actual pollers in /workers)
```

### Layer rules

1. **Routers** — validate input, call services, map errors → HTTP.
2. **Services** — transactions, authorization checks, orchestration.
3. **Integrations** — S3/Redis/SQS clients; no business rules.
4. **Models** — persistence only; no HTTP knowledge.

---

## 6. Core domain model (logical)

```
User ──┬── StorageQuota (plan, bytes_used, bytes_limit)
       ├── Folder (tree: parent_id, path / materialized path)
       ├── File ── FileObject (s3_key, size, checksum, mime)
       │         └── FileVersion (optional later)
       ├── Share ── SharePermission (role: viewer | editor | owner)
       ├── TrashEntry (soft-delete metadata, expires_at)
       └── UploadSession (multipart: upload_id, parts, status)

Job / Outbox (optional) — durable enqueue for critical side effects
AuditEvent — security-relevant actions (Phase 15+)
```

### Important invariants

- **Bytes live in S3; names, folders, ACLs live in Postgres.**
- Deleting a file soft-deletes metadata first (trash); hard delete removes S3 object asynchronously.
- Quota is checked **before** completing an upload; usage updated in the same DB transaction as file create (with Redis as a fast approximate counter if needed).
- Shares never bypass trash / owner checks without an explicit permission path.

---

## 7. Request flows (canonical)

### 7.1 Upload (simple, Phase 06)

1. Client `POST /files/upload-url` with name, size, mime, `folder_id`.
2. API checks auth + folder ACL + quota headroom.
3. API creates `pending` File row + S3 key; returns **presigned PUT** (or POST policy).
4. Client uploads bytes **directly to S3**.
5. Client `POST /files/{id}/complete` (or webhook/S3 event).
6. API verifies object exists/size (HeadObject), marks file `ready`, updates quota, enqueues thumbnail/index jobs.

### 7.2 Download (Phase 07)

1. Client `GET /files/{id}/download-url`.
2. API checks ACL.
3. API returns short-lived **presigned GET**.
4. Client downloads from S3.

### 7.3 Multipart / resumable (Phase 14)

Same as upload, but `UploadSession` + S3 multipart APIs; complete only after all parts verified.

### 7.4 Background work (Phase 12+)

```
API / S3 event → SQS message → Worker → update Postgres (+ write preview to S3)
```

Workers are idempotent: same `job_id` / `file_id` can be retried safely.

---

## 8. Auth & tenancy (Phase 03–04)

**MVP recommendation:** email/password (or magic link) + **JWT access token** (short) + **refresh token** (HttpOnly cookie or rotating store in Redis/Postgres).

| Concern | Approach |
|---------|----------|
| Password hashing | Argon2id |
| Authorization | Resource checks in services (owner / share role) |
| Tenancy | Single-user ownership of folders/files; shares grant cross-user access |
| Quota | Per-user `bytes_used` / `bytes_limit`; plan table for billing later |

Cognito can replace credential storage later without changing the resource ACL model if we keep `user_id` as the principal.

---

## 9. Storage design (S3)

```
s3://fdrive-{env}/
  users/{user_id}/files/{file_id}/original
  users/{user_id}/files/{file_id}/versions/{version_id}   # optional
  users/{user_id}/files/{file_id}/previews/{variant}      # thumb, pdf page, etc.
```

| Setting | Intent |
|---------|--------|
| Private bucket | No public reads |
| SSE-S3 or SSE-KMS | Encryption at rest |
| Lifecycle rules | Expire incomplete multipart; move cold trash to cheaper tier later |
| Versioning | Optional; start off, enable if audit needs it |
| CORS | Only app origins for browser PUT/GET |

---

## 10. API surface (initial modules)

Versioned: `/api/v1/...`

| Module | Examples | Phase |
|--------|----------|-------|
| Auth | register-account, login, refresh-token, logout | 03 |
| Account | profile, storage-quota | 04 |
| Folders | create, list, rename, move, tree | 05 |
| Files | request-upload-url, complete-upload, metadata | 06 |
| Download | request-download-url | 07 |
| Manage | rename, move, copy | 08 |
| Trash | soft-delete, restore, purge | 09 |
| Shares | create link / user share, roles | 10 |
| Search | query by name (± content later) | 11 |
| Previews | thumbnail / preview URL | 13 |
| Uploads | multipart session APIs | 14 |
| Billing | plans, portal | 21 |

Health: `GET /health` (liveness), `GET /ready` (DB/Redis).

---

## 11. Cross-cutting concerns

| Concern | Approach |
|---------|----------|
| Config | Env vars + Pydantic Settings; secrets in AWS SM/SSM in prod |
| Migrations | Alembic only — no auto-create in prod |
| Logging | Structured JSON logs; `request_id` / `user_id` correlation |
| Metrics | Latency, error rate, upload success, queue depth (Phase 20) |
| Rate limits | Redis token bucket on auth + upload-url |
| CORS | Explicit SPA origin allowlist |
| Idempotency | Keys on `complete upload` and share create where retries happen |

---

## 12. Environments

| Env | Purpose |
|-----|---------|
| `local` | docker-compose: Postgres, Redis, MinIO (S3), LocalStack SQS or ElasticMQ, API, worker, Vite |
| `staging` | AWS mirror of prod at smaller size |
| `prod` | Multi-AZ data stores; autoscaled API/workers |

---

## 13. Security baseline (expanded in Phase 15)

- Presigned URLs short TTL; scoped keys only.
- Server-side ACL on every metadata mutation.
- No trusting client-reported size without HeadObject verification.
- Soft-delete + delayed hard purge for ransomware / accidental delete recovery.
- Principle of least privilege IAM for API vs workers.
- Dependency scanning + secret scanning in CI (Phase 19).

---

## 14. Phase mapping → architecture slices

| Phase | Delivers |
|-------|----------|
| 01 | Repo, compose, CI skeleton, this architecture |
| 02 | Postgres schema + Alembic + core models |
| 03 | Auth + protected routes |
| 04 | User profile + quota enforcement hooks |
| 05 | Folder tree APIs + UI |
| 06–07 | Presigned upload/download path |
| 08–09 | Rename/move + trash/restore |
| 10 | Shares + permission checks everywhere |
| 11 | Search (Postgres first) |
| 12 | SQS workers scaffold |
| 13 | Preview/thumbnail pipeline |
| 14 | Multipart resumable uploads |
| 15 | Hardening (WAF, locks, audits) |
| 16 | Frontend polish |
| 17 | Tests + load tests |
| 18–20 | Infra, CI/CD, observability |
| 21–23 | Billing, launch, scale |

---

## 15. Open questions (product / ops)

Answer these before or during the listed phases; architecture above stays valid either way.

1. **Single-user personal drive vs team workspaces?** (affects tenancy — Phase 02/10)
2. **Max file size & free tier quota?** (Phase 04/14/21)
3. **Public share links without login?** (Phase 10)
4. **Virus scanning required at MVP?** (worker hook — Phase 12/15)
5. **Landing/marketing site in same repo?** (optional Next.js later; app stays Vite)

---

## 16. Immediate next step

**Phase 01 — Project Foundation**

1. Scaffold monorepo (`apps/web`, `apps/api`, `workers`).
2. `docker-compose` for Postgres + Redis + MinIO.
3. Minimal FastAPI hello + Vite app shell.
4. Shared env example files; no secrets committed.

Architecture is the contract; implementation follows phases in order unless a dependency forces a small pull-forward (e.g. Redis client when auth lands).
