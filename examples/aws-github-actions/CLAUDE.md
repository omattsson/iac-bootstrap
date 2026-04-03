# Acme Infrastructure Automation (AWS)

You are working in an infrastructure-as-code workspace for Acme's AWS platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `terraform-aws-*` | Reusable AWS resource modules |
| **Environments** | `environments/` | Terraform workspace configs per environment |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/acme/terraform-aws-{name}?ref={tag}
```

Version tags managed in `environments/{env}/versions.tf` → `module_versions` locals.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `acme-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from environment layer
- `vpc_id` — VPC ID (where networking is required)
- `subnet_ids` — Subnet IDs (where networking is required)
- `account_id` — AWS account ID

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3 Bucket: `{prefix}-s3-{suffix}` (max 63 chars, globally unique)
- Lambda: `{prefix}-lambda-{suffix}` (max 64 chars)
- All names sanitized: `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Environment Structure

```
environments/{env}/
├── main.tf         — Root module
├── variables.tf    — Environment-specific variables
├── versions.tf     — Module version pins + backend config
└── outputs.tf      — Environment outputs
```
S3 + DynamoDB backend for all environments. Separate state bucket per environment.

---

## Coding Standards

### Terraform Files (`terraform-aws-*/**/*.tf`)

**File organization:**
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by AWS resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs (at minimum: `name`, `id`, and `arn`)
- `versions.tf` — terraform and provider version constraints

**Resource conventions:**
- Single resources use identifier `"default"` (e.g., `aws_s3_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Boolean toggles use `count`
- Tags: `merge(var.env_default_tags, var.tags)` — always

**Naming pattern:**
```hcl
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-s3-${local.name_suffix}", 0, 63)
```

**Provider versions:**
```hcl
aws = { source = "hashicorp/aws", version = ">=5.0,<6.0" }
```

**No hardcoded secrets, account IDs, or credentials in module code. Use IAM roles and AWS Secrets Manager.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "aws" {}
```

- All tests: `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in `variables {}` block:
  ```hcl
  variables {
    prefix           = "test-auto"
    region           = "us-east-1"
    tags             = {}
    env_default_tags = { managed_by = "Terraform" }
  }
  ```
- One test file per concern: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.

### Pipeline Files (`.github/workflows/**/*.yml`)

Two-stage: Plan → Apply (on protected branches with approval). OIDC-based auth (no long-lived credentials). Provider caching.

---

## Behavioral Rules

- DO NOT run `terraform apply` or `terraform destroy` without explicit approval
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests
- ALWAYS use `mock_provider "aws" {}` in tests
- ALWAYS use OIDC for GitHub Actions authentication — never static access keys

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — shared modules, environment-specific overrides only
3. **No hardcoded secrets** — use IAM roles, AWS Secrets Manager, OIDC
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
