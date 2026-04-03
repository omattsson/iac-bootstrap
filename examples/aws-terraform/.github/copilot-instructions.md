# Workspace Instructions — Acme Infrastructure Automation

## Workspace Overview

This workspace contains infrastructure-as-code for Acme's AWS platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable AWS resource modules |
| **Stacks** | `environments/` | Per-environment Terraform root configs |
| **Pipelines** | `.github/workflows/` | GitHub Actions CI/CD workflows |

## Module Source Convention

```
git::https://github.com/acme/tf-module-{name}.git?ref={tag}
```

Version tags managed in `environments/{environment}/{stack}/versions.tf` → `module_versions` locals.

## Standard Variable Set (Cross-Module)

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `app-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from stack inputs

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3 bucket: `{prefix}-{suffix}` (globally unique, lowercase, max 63 chars)
- IAM role: `{prefix}-{suffix}` (max 64 chars)
- All names lowercase with `lower(regexreplace(var.suffix, "[^0-9a-zA-Z]+", "-"))`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Always merge environment defaults with resource-specific tags. `var.tags` wins on key conflicts.
Required tags: `Environment`, `Product`, `ManagedBy = "Terraform"`.

## Stack Hierarchy

```
environments/{environment}/{stack}/
├── main.tf       # Module calls + provider
├── variables.tf  # Stack-level variables
├── outputs.tf    # Stack outputs
├── backend.tf    # S3 remote state backend
└── versions.tf   # Provider + module version pins
```

- S3 state bucket: `acme-terraform-state-{account_id}`
- Key pattern: `{environment}/{stack}/terraform.tfstate`
- DynamoDB lock table: `acme-terraform-locks`

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config in reusable modules, environment-specific overrides in stacks
3. **No hardcoded secrets** — use OIDC, SSM Parameter Store, or Secrets Manager
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
