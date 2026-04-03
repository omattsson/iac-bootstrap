# Acme Infrastructure Automation (GCP)

You are working in an infrastructure-as-code workspace for Acme's Google Cloud platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `terraform-google-*` | Reusable GCP resource modules |
| **Environments** | `environments/` | Terraform workspace configs per environment |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/acme/terraform-google-{name}?ref={tag}
```

Version tags managed in `environments/{env}/versions.tf` → `module_versions` locals.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `acme-uc1-dev`)
- `project` — GCP project ID (e.g., `acme-dev-123456`)
- `region` — GCP region (default: `us-central1`)
- `labels` — Additional labels (`map(string)`)
- `env_default_labels` — Default labels from environment layer
- `network` — VPC network name (where networking is required)
- `subnetwork` — Subnetwork name (where networking is required)

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- GCS Bucket: `{prefix}-gcs-{suffix}` (max 63 chars, globally unique, lowercase)
- Cloud Run: `{prefix}-run-{suffix}` (max 49 chars per service)
- All names sanitized: `replace(lower(var.suffix), "/[^0-9a-z-]+/", "-")`
- Optional `full_name` override on most modules

## Labeling Standard

```hcl
local.labels = merge(var.env_default_labels, var.labels)
```
GCP uses `labels` not `tags`. Keys/values must be lowercase, max 63 chars, no spaces.
Required labels: `environment`, `product`, `managed_by = "terraform"`.

## Environment Structure

```
environments/{env}/
├── main.tf         — Root module
├── variables.tf    — Environment-specific variables
├── versions.tf     — Module version pins + backend config
└── outputs.tf      — Environment outputs
```
GCS backend for all environments. Separate state bucket per environment.

---

## Coding Standards

### Terraform Files (`terraform-google-*/**/*.tf`)

**File organization:**
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by GCP resource type
- `locals.tf` — name construction, label merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs (at minimum: `name` and `id`)
- `versions.tf` — terraform and provider version constraints

**Resource conventions:**
- Single resources use identifier `"default"` (e.g., `google_storage_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Boolean toggles use `count`
- Labels: `merge(var.env_default_labels, var.labels)` — always

**Naming pattern:**
```hcl
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, {max_length})
```
<!-- Examples: GCS bucket uses 'acme-gcs-mysuffix' (max 63), Cloud Run uses 'acme-run-mysuffix' (max 49).
     Note: GCS buckets use `location` not `region`; Cloud Run and Cloud SQL use `region`. -->

**Provider versions:**
```hcl
google = { source = "hashicorp/google", version = ">=5.0,<6.0" }
```

**No hardcoded secrets, project IDs, or credentials in module code. Use Workload Identity and Secret Manager.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "google" {}
```

- All tests: `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in `variables {}` block:
  ```hcl
  variables {
    prefix             = "test-auto"
    project            = "acme-test-000000"
    region             = "us-central1"
    labels             = {}
    env_default_labels = { managed_by = "terraform" }
  }
  ```
- One test file per concern: `naming.tftest.hcl`, `labels.tftest.hcl`, etc.

### Pipeline Files (`.github/workflows/**/*.yml`)

Two-stage: Plan → Apply (on protected branches with approval). Workload Identity Federation (no key files). Provider caching.

---

## Behavioral Rules

- DO NOT run `terraform apply` or `terraform destroy` without explicit approval
- DO NOT hardcode secrets, project IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests
- ALWAYS use `mock_provider "google" {}` in tests
- ALWAYS use Workload Identity Federation for GitHub Actions — never service account key files

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — shared modules, environment-specific overrides only
3. **No hardcoded secrets** — use Workload Identity, Secret Manager, OIDC
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
