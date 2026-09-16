# Scaling guide (Phase 23)

FDrive stays a **modular monolith** until metrics force a split.

## Scale-out levers (in order)

1. **Horizontal API** — raise ECS desired count behind the ALB; sessions are JWT so sticky sessions are not required
2. **Workers** — scale SQS consumers independently of the API
3. **Postgres** — larger instance class; read replica only if read-heavy browse/search justifies it
4. **Redis** — ElastiCache node size for rate-limit / cache pressure
5. **S3** — already scales; watch request rates and multipart part size tuning
6. **Search** — name search uses Postgres `pg_trgm` GIN indexes (still simple `ILIKE`). Only add OpenSearch if search load or ranking needs grow beyond that

## Split candidates (only when needed)

| Symptom | Candidate extract |
|---------|-------------------|
| Thumbnail backlog grows with API load | Dedicated media worker fleet (already separate process) |
| Auth abuse / bot traffic | Edge WAF + dedicated auth rate tier |
| Billing webhooks noisy | Small billing service listening to Stripe |

## Capacity cues

| Signal | Action |
|--------|--------|
| API p95 > 300 ms sustained | Add API tasks; check DB slow queries |
| SQS oldest message age high | Add workers; raise visibility timeout carefully |
| RDS CPU > 70% | Upsize or index hot paths (`files.owner_id`, folder lists) |
| S3 5xx / slow PUT | Increase part size for multipart; retry client-side |

Keep product features in the monolith until an extract removes a real bottleneck.
