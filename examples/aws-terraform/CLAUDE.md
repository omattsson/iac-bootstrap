# Acme Infrastructure Automation

You are working in an infrastructure-as-code workspace for Acme's AWS platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable AWS resource modules |
| **Stacks** | `environments/` | Per-environment Terraform root configs |
| **Pipelines** | `.github/workflows/` | GitHub Actions CI/CD workflows |

## Module Source Convention

```
git::https://github.com/acme/tf-module-{name}.git?ref={tag}
```

Version tags managed in `environments/{environment}/{stack}/versions.tf` → `module_versions` locals.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `app-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from stack inputs

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3 bucket: `{prefix}-{suffix}` (globally unique, lowercase, max 63 chars)
- IAM role: `{prefix}-{suffix}` (max 64 chars)
- All names lowercase: `lower(replace(var.suffix, "/[^0-9a-zA-Z]+/", "-"))`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Required tags: `Environment`, `Product`, `ManagedBy = "Terraform"`.

## Stack Hierarchy

```
environments/{environment}/{stack}/
├── main.tf          # Module calls + provider config
├── variables.tf     # Stack-level variables
├── outputs.tf       # Stack outputs
├── backend.tf       # S3 backend config
└── versions.tf      # Provider + module version pins
```

S3 backend: `acme-terraform-state-{account_id}` / `{environment}/{stack}/terraform.tfstate`  
DynamoDB lock table: `acme-terraform-locks`

---

## Coding Standards

### Terraform Files (`tf-module-*/**/*.tf`)

**File organization:**
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by AWS resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs (at minimum: `name` and `id`/`arn`)
- `versions.tf` — terraform and provider version constraints

**Resource conventions:**
- Single resources use identifier `"default"` (e.g., `aws_s3_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Boolean toggles use `count`
- Tags: `merge(var.env_default_tags, var.tags)` — always

**Naming pattern:**
```hcl
local.name = var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}"
```

**Provider versions:**
```hcl
aws = { source = "hashicorp/aws", version = ">=5.0,<6.0" }
```

**No hardcoded secrets, account IDs, or credentials in module code.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "aws" {}

override_data {
  target = data.aws_caller_identity.current
  values = {
    account_id = "123456789012"
    arn        = "arn:aws:iam::123456789012:root"
    user_id    = "123456789012"
  }
}
```

- All tests: `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in `variables {}` block
- One test file per concern: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.

### Stack Files (`environments/**/*.tf`)

Hierarchy: `environments/{environment}/{stack}/`

State backend:
- One S3 key per stack (one deployable unit)
- DynamoDB for state locking
- Encryption enabled

Module versions pinned in `versions.tf` locals. Never hardcode module refs in `main.tf`.

### Pipelines (`.github/workflows/*.yml`)

Two-stage: Plan → Apply (on protected branches with approval). OIDC-based auth (no long-lived credentials). Provider caching.

---

## Behavioral Rules

- DO NOT run `terraform apply` or `terraform destroy` without explicit approval
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests
- ALWAYS use `mock_provider "aws" {}` in tests
- ALWAYS use OIDC for authentication — never IAM user access keys in pipelines

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — shared config in reusable modules, per-environment overrides only in stacks
3. **No hardcoded secrets** — use OIDC, SSM Parameter Store, or Secrets Manager
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
