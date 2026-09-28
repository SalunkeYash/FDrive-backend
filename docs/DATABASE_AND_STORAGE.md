# FDrive — Database & Storage Guide

How metadata and file bytes are stored, why that shape exists, where each table is used, and how to inspect Postgres + MinIO locally.

---

## Big idea

FDrive splits **metadata in Postgres** from **file bytes in S3 (MinIO locally)**.

| Store | Holds | Why |
|-------|--------|-----|
| **Postgres** | Users, folders, file names, sizes, shares, trash, auth tokens | Fast queries, constraints, transactions |
| **S3 / MinIO** | Original files + thumbnails | Cheap, scalable blobs; API never streams large files |
| **Redis** | Rate limits / cache (not the main drive tree) | Ephemeral |

A “file” in the product is two pieces:

1. A row in `files` (name, folder, size, status)
2. A row in `file_objects` (bucket + S3 key pointing at the bytes)

**Rule:** Bytes live in object storage; names, folders, and ACLs live in Postgres.

---

## Tables — what / why / where used

### `users`

| | |
|--|--|
| **What** | Account identity + quota: `email`, `password_hash`, `display_name`, `bytes_used`, `bytes_limit` |
| **Why** | One place for login and storage limits (default free tier ~5 GiB) |
| **Used by** | Auth (register/login), profile / display name, account menu storage bar, upload quota checks |

---

### `folders`

| | |
|--|--|
| **What** | Folder tree: `parent_id` (null = My Drive root), `name`, `path` (materialized path like `/uuid/uuid/`), soft-delete flags |
| **Why** | Nested Drive layout without scanning S3. Unique `(owner_id, parent_id, name)` prevents duplicate names in the same place. `path` helps tree / move / descendant checks |
| **Used by** | My Drive, open folder, create/rename/move, breadcrumbs, Organize → Move, drag-drop folder upload |

Example tree:

```text
My Drive (parent_id = null)
 ├── ABC
 └── Documents
      ├── Marksheets
      └── Photos
           └── raw
```

---

### `files`

| | |
|--|--|
| **What** | File metadata: `name`, `mime_type`, `size_bytes`, `folder_id`, `status` (`pending` → `ready` / `failed`), trash flags |
| **Why** | Listing and filters stay in DB. `pending` exists because upload is: create row → client PUTs to S3 → `complete-upload` marks `ready` and updates quota |
| **Used by** | File grid/list, open/download, rename/move/copy, Type/Modified filters, trash |

---

### `file_objects`

| | |
|--|--|
| **What** | Pointer to S3: `s3_bucket`, `s3_key`, etag/checksum |
| **Why** | Bytes must not live in Postgres. Download/preview/thumbnail only need the key to mint a presigned URL |
| **Used by** | Upload complete, download URL, preview URL, thumbnail worker |

Object key layout:

```text
users/{user_id}/files/{file_id}/original
users/{user_id}/files/{file_id}/previews/thumb_v2
```

The key ends in `original` (no `.jpg`). The **display name** (`DSC0647.JPG`) stays in `files.name`. That is why MinIO Console often cannot “preview” by extension — use **Download** in MinIO, or open the file in the FDrive app.

---

### `shares`

| | |
|--|--|
| **What** | Who can access what: `resource_type` + `resource_id` (file or folder), `grantee_user_id` **or** `token` (public link), `role` (`viewer` / `editor`) |
| **Why** | One polymorphic table instead of separate file/folder share tables. Link share = null grantee + token |
| **Used by** | Share modal, People filter (“Shared by me”), `/share/:token` page |

---

### `trash_entries`

| | |
|--|--|
| **What** | Soft-delete ledger: resource id, optional restore folder, `expires_at` for later purge |
| **Why** | Bin can restore or permanently delete on a schedule. Items also flip `is_trashed` on `files` / `folders` |
| **Used by** | Move to bin, Bin page, restore / delete forever |

---

### `upload_sessions`

| | |
|--|--|
| **What** | Multipart / resumable upload state (`s3_upload_id`, parts, status) |
| **Why** | Large files need chunked S3 uploads; this tracks progress across requests |
| **Used by** | Large / resumable upload APIs |

---

### `refresh_tokens`

| | |
|--|--|
| **What** | Hashed refresh tokens + expiry / revoke |
| **Why** | Logout and rotation without trusting a forever JWT. Access token is short-lived; refresh lives here hashed |
| **Used by** | Login, refresh-token, logout |

---

### `audit_events`

| | |
|--|--|
| **What** | Security log: actor, action, resource, IP, JSON metadata |
| **Why** | Forensics / abuse investigation without mixing into product tables |
| **Used by** | Security hardening paths (sensitive actions) |

---

## Mental model

```text
User
 ├─ folders (tree via parent_id)
 │    └─ files (metadata)
 │         └─ file_objects → S3 key
 ├─ shares (ACL / links on file|folder ids)
 ├─ trash_entries (bin schedule)
 ├─ refresh_tokens (sessions)
 └─ audit_events (security log)
```

---

## How a typical upload uses this

```text
1. POST request-upload-url
   → insert files (status=pending) + file_objects (s3_key)
   → check users.bytes_used + size ≤ bytes_limit

2. Browser PUT bytes straight to MinIO/S3 (not through FastAPI)

3. POST complete-upload
   → HeadObject verify size
   → files.status = ready
   → users.bytes_used += size
   → enqueue generate_thumbnail (worker writes preview object in S3)
```

Open / download: API checks ownership or share → returns **presigned GET** → browser hits S3.

---

## Real example (from local data)

**File:** `DSC0647.JPG`

| Field | Example value |
|--------|----------------|
| `files.id` | UUID for the file |
| `files.name` | `DSC0647.JPG` |
| `files.mime_type` | `image/jpeg` |
| `files.status` | `ready` |
| `files.folder_id` | Photos folder under Documents |
| `file_objects.s3_bucket` | `fdrive` |
| `file_objects.s3_key` | `users/{user_id}/files/{file_id}/original` |

On MinIO for the same file id you may also see:

```text
…/original
…/previews/thumb
…/previews/thumb_v2   ← EXIF-corrected thumbnail
```

UI: list from Postgres → thumbnail from `previews/thumb_v2` → Open uses a presigned URL for `original`.

---

## How to see the database (Postgres)

### Prerequisites

```bash
# from repo root
docker compose up -d postgres
```

### Connection details (Beekeeper, DBeaver, TablePlus, pgAdmin, etc.)

| Field | Value |
|--------|--------|
| Type | PostgreSQL |
| Host | `localhost` |
| **Port** | **`5432`** |
| Database | `fdrive` |
| User | `fdrive` |
| Password | `fdrive` |
| SSL | Off (local) |

### Terminal (psql)

```bash
docker exec -it fdrive-postgres-1 psql -U fdrive -d fdrive
```

Useful SQL:

```sql
\dt
SELECT id, email, display_name, bytes_used, bytes_limit FROM users;
SELECT id, name, parent_id, path, is_trashed FROM folders;
SELECT id, name, folder_id, size_bytes, status, mime_type FROM files LIMIT 20;
SELECT file_id, s3_bucket, s3_key FROM file_objects LIMIT 10;
SELECT resource_type, resource_id, role, token FROM shares LIMIT 10;
```

---

## How to see cloud storage (MinIO)

### Prerequisites

```bash
docker compose up -d minio
```

### Browser console (easiest)

| | |
|--|--|
| **URL** | **http://localhost:9001** |
| User | `minioadmin` |
| Password | `minioadmin` |

Open bucket **`fdrive`** → browse `users/…/files/…/original` and `previews/`.

If Console says **Preview unavailable** for `original`, that is expected (key has no file extension). Use **Download**, or open the file in the FDrive web app.

### S3 API endpoint

| | |
|--|--|
| **URL** | **http://localhost:9000** |
| Access key | `minioadmin` |
| Secret key | `minioadmin` |
| Bucket | `fdrive` |

### CLI list (optional)

```bash
docker run --rm --entrypoint /bin/sh --network fdrive_default minio/mc:latest -c '
mc alias set local http://minio:9000 minioadmin minioadmin
mc ls local/fdrive --recursive | head -40
'
```

---

## Local ports cheat sheet

| Service | Port | What you see |
|---------|------|----------------|
| **Postgres** | **5432** | Tables / SQL (Beekeeper, psql) |
| **MinIO Console** | **9001** | Browse buckets & objects in the browser |
| **MinIO S3 API** | **9000** | Programmatic / AWS-CLI style access |
| Redis | 6379 | Cache / rate limits |
| ElasticMQ (SQS) | 9324 | Local job queue |
| FastAPI | 8000 | API + OpenAPI docs `/docs` |
| Vite web app | 5173 | FDrive UI |

Start everything:

```bash
docker compose up -d
```

---

## Related code

- Models: `app/models/entities.py`
- Architecture overview: `docs/ARCHITECTURE.md`
- S3 key helpers: `app/integrations/s3.py`
