# Acme Infrastructure Automation

You are working in an infrastructure-as-code workspace for Acme's AWS platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable AWS resource modules |
| **Orchestration** | `infrastructure-live/` | Terragrunt config for all environments |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/acme-corp/tf-module-{name}.git?ref={tag}
```

Version tags managed in `account.hcl` → `module_tags` local.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `acme-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — Additional resource tags (`map(string)`)
- `env_default_tags` — Default tags from Terragrunt inputs

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- S3 Buckets: `{prefix}-s3-{suffix}` (globally unique, max 63 chars)
- All names sanitized: `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Environment Hierarchy

```
infrastructure-live/
├── terragrunt.hcl              # root config
└── {account}/
    ├── account.hcl             # account ID, module versions
    └── {region}/
        ├── region.hcl          # region config
        └── {stack}/
            └── {component}/
                └── terragrunt.hcl
```

Hierarchy files:
- `account.hcl` → AWS account ID, module versions
- `region.hcl` → Region
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
- `outputs.tf` — module outputs (at minimum: `name`/`arn` and `id`)
- `versions.tf` — terraform and provider version constraints

**Resource conventions:**
- Single resources use identifier `"default"` (e.g., `aws_s3_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Boolean toggles use `count`
- Tags: `merge(var.env_default_tags, var.tags)` — always
- Never hardcode account IDs — use `data.aws_caller_identity.current.account_id`

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

**Standard test variables:**
```hcl
variables {
  prefix           = "test-auto"
  region           = "us-east-1"
  tags             = {}
  env_default_tags = { managed_by = "Terraform" }
}
```

---

## Authentication & CI/CD

- **Auth:** OIDC via `aws-actions/configure-aws-credentials@v4` — no static credentials
- **State:** S3 backend with DynamoDB locking
- **Pipeline trigger:** Push to `main` triggers plan; manual approval triggers apply
