# Workspace Instructions — Acme Infrastructure Automation (AWS)

## Workspace Overview

This workspace contains infrastructure-as-code for Acme's AWS platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `terraform-aws-*` | Reusable AWS resource modules |
| **Environments** | `environments/` | Terraform workspace configs per environment |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/acme/terraform-aws-{name}?ref={tag}
```

Version tags managed in `environments/{env}/versions.tf` → `module_versions` locals.

## Standard Variable Set (Cross-Module)

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `acme-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from environment layer
- `vpc_id` — VPC to deploy resources into (where networking is required)
- `subnet_ids` — Subnet IDs for resource placement (where networking is required)
- `account_id` — AWS account ID

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3 Bucket: `{prefix}-s3-{suffix}` (globally unique, max 63 chars)
- Lambda: `{prefix}-lambda-{suffix}` (max 64 chars)
- All names sanitized with `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Always merge environment defaults with resource-specific tags. `var.tags` wins on key conflicts.
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Environment Structure

```
environments/{env}/
├── main.tf         — Root module
├── variables.tf    — Environment-specific variables
├── versions.tf     — Module version pins + backend config
└── outputs.tf      — Environment outputs
```

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — shared modules, environment-specific overrides only
3. **No hardcoded secrets** — use IAM roles, AWS Secrets Manager, OIDC
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
