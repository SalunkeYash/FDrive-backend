# Production launch checklist (Phase 22)

Use this before pointing a public DNS name at FDrive.

## Pre-flight

- [ ] `ENVIRONMENT=prod` and `ENABLE_API_DOCS=false`
- [ ] Strong unique `JWT_SECRET` in Secrets Manager
- [ ] Postgres multi-AZ (or at least automated backups) from Terraform
- [ ] S3 bucket private + CORS limited to SPA origin
- [ ] SQS `fdrive-jobs` wired; worker service healthy
- [ ] Redis available for rate limits
- [ ] Alembic `upgrade head` run successfully on prod DB
- [ ] Custom domain + TLS on ALB
- [ ] SPA built with production API base URL / same-origin proxy

## Security

- [ ] Auth rate limits verified under load
- [ ] Dependency scan clean (`pip-audit` / `npm audit` as policy allows)
- [ ] No secrets in git history or images
- [ ] Backup restore drill for Postgres completed once

## Smoke test (prod)

1. Register + login
2. Create folder, upload small file, download
3. Search by name
4. Move file to trash and restore
5. Create share link and open it
6. Confirm worker logs a thumbnail job for an image upload

## Go / no-go

- [ ] On-call contact known
- [ ] CloudWatch alarms for 5xx / SQS age / RDS storage
- [ ] Rollback plan: previous ECS task definition revision ready
