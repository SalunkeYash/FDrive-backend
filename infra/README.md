# FDrive AWS infrastructure (Phase 18)

Terraform layout for staging/prod. Apply only after filling `terraform.tfvars` and authenticating the AWS CLI.

## Modules

| Path | Responsibility |
|------|----------------|
| `terraform/` | Root stack (providers, wiring) |
| `terraform/modules/network` | VPC, public/private subnets, NAT |
| `terraform/modules/data` | RDS Postgres, ElastiCache Redis, S3, SQS |
| `terraform/modules/compute` | ECS cluster placeholders for API + workers |

## Bootstrap

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit project_name, aws_region, db password via TF_VAR / Secrets Manager later
terraform init
terraform plan
```

Do **not** commit real secrets or `terraform.tfstate`.

## Design notes

- Private subnets for RDS, Redis, ECS tasks
- Public subnets for ALB (+ NAT for egress)
- S3 bucket private; CORS limited to the SPA origin
- SQS queue `fdrive-jobs` for thumbnail / purge workers
- IAM least privilege is sketched; tighten before prod apply
