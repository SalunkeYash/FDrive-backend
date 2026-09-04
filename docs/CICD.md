# CI/CD notes (Phase 19)

## Pipelines

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `.github/workflows/ci.yml` | PR + push | Lint, migrate, pytest, web build |
| `.github/workflows/cd.yml` | push to `main` | Build/push Docker images to GHCR |

## Images

- `ghcr.io/<org>/fdrive/api`
- `ghcr.io/<org>/fdrive/worker`
- `ghcr.io/<org>/fdrive/web`

## Next wiring (after Terraform apply)

1. Create ECS task definitions referencing GHCR images
2. Store secrets in AWS Secrets Manager (`DATABASE_URL`, `JWT_SECRET`, …)
3. Replace `deploy-staging-stub` with `aws ecs update-service`
4. Run `alembic upgrade head` as a one-shot task before rolling API
