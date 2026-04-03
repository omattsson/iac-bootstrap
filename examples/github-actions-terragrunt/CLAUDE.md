# Acme Infrastructure Automation

You are working in an infrastructure-as-code workspace for Acme's AWS platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable AWS resource modules |
| **Orchestration** | `infrastructure-config/` | Terragrunt config for all environments |
| **Pipelines** | `.github/workflows/` | GitHub Actions workflow templates |

## Module Source Convention

```
git::https://github.com/acme-infra/tf-module-{name}?ref={tag}
```

Version tags managed in `account.hcl` → `module_tags` local.

## Standard Variable Set

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
- All names sanitized: `regexreplace(var.suffix, "[^0-9A-Za-z]+", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Terragrunt Hierarchy

```
config/{environment}/{region}/{stack}/{component}/terragrunt.hcl
```
- `account.hcl` → Account ID, module versions
- `region.hcl` → AWS region, availability zones
- `stack.hcl` → Stack name, prefix
- `_envcommon/*.hcl` → Shared module configs

---

## Coding Standards

### Terraform Files (`tf-module-*/**/*.tf`)

**File organization:**
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by AWS resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs (at minimum: `name` and `id`)
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

**No hardcoded secrets, account IDs, or credentials in module code.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "aws" {}

variables {
  prefix           = "test-auto"
  region           = "us-east-1"
  tags             = {}
  env_default_tags = { managed_by = "Terraform" }
  account_id       = "123456789012"
}
```

- All tests: `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in `variables {}` block
- One test file per concern: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.

### Terragrunt Files (`infrastructure-config/**/*.hcl`)

Hierarchy: account.hcl → region.hcl → stack.hcl → component/terragrunt.hcl

Shared config in `_envcommon/`:
- Read hierarchy variables from parent files
- Define source URL pointing to module repo
- Declare dependencies with realistic mock outputs
- Map hierarchy variables to module inputs

Version tags from `account.hcl`. Never hardcode versions in components.

### Pipelines (`.github/workflows/*.yml`)

Two-stage: Plan → Apply (on protected branches with environment approval). OIDC-based auth (no long-lived credentials).

---

## Behavioral Rules

- DO NOT run `terraform apply` or `terraform destroy` without explicit approval
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests
- ALWAYS use `mock_provider "aws" {}` in tests
- ALWAYS provide `mock_outputs` in Terragrunt dependency blocks

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config in `_envcommon`, variables flow from hierarchy
3. **No hardcoded secrets** — use Secrets Manager, OIDC, or Terragrunt inputs
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
