# Workspace Instructions — Acme Infrastructure Automation (GCP)

## Workspace Overview

This workspace contains infrastructure-as-code for Acme's Google Cloud platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `terraform-google-*` | Reusable GCP resource modules |
| **Environments** | `environments/` | Terraform workspace configs per environment |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/acme/terraform-google-{name}?ref={tag}
```

Version tags managed in `environments/{env}/versions.tf` → `module_versions` locals.

## Standard Variable Set (Cross-Module)

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
- GCS Bucket: `{prefix}-gcs-{suffix}` (globally unique, max 63 chars, lowercase)
- Cloud Run: `{prefix}-run-{suffix}` (max 49 chars per service name)
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

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — shared modules, environment-specific overrides only
3. **No hardcoded secrets** — use Workload Identity, Secret Manager, OIDC
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
