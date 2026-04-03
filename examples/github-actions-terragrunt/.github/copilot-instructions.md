# Workspace Instructions — Acme Infrastructure Automation

## Workspace Overview

This workspace contains infrastructure-as-code for Acme's AWS platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable AWS resource modules |
| **Orchestration** | `infrastructure-config/` | Terragrunt config for all environments |
| **Pipelines** | `.github/workflows/` | GitHub Actions workflow templates |

## Module Source Convention

```
git::https://github.com/acme-infra/tf-module-{name}?ref={tag}
```

Version tags managed in `account.hcl` → `module_tags` local.

## Standard Variable Set (Cross-Module)

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `app-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from Terragrunt inputs
- `account_id` — AWS account ID

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3: `{prefix}-s3-{suffix}` (lowercase, max 63 chars)
- IAM roles: `{prefix}-role-{suffix}` (max 64 chars)
- All names sanitized with `regexreplace(var.suffix, "[^0-9A-Za-z]+", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Always merge environment defaults with resource-specific tags. `var.tags` wins on key conflicts.
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Terragrunt Hierarchy

```
config/{environment}/{region}/{stack}/{component}/terragrunt.hcl
```
- `account.hcl` → Account ID, module versions
- `region.hcl` → AWS region, availability zones
- `stack.hcl` → Stack name, prefix
- `_envcommon/*.hcl` → Shared module configs with dependencies and inputs

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config lives in `_envcommon`, variables flow from hierarchy
3. **No hardcoded secrets** — use Secrets Manager, OIDC, or Terragrunt inputs
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
