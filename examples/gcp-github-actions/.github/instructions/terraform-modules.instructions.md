---
description: "Terraform coding standards for Acme GCP modules. Use when writing or modifying .tf files including resources, variables, outputs, locals, and provider configurations."
applyTo: "terraform-google-*/**/*.tf"
---

# Terraform Module Standards (GCP)

## File Organization
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by GCP resource type (e.g., `storage_bucket.tf`, `cloud_run_service.tf`)
- `locals.tf` — name construction, label merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs
- `versions.tf` — terraform and provider version constraints

## Resource Conventions
- All single resources use identifier `"default"` (e.g., `google_storage_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Use `count` for boolean on/off features
- Labels: `merge(var.env_default_labels, var.labels)` — always (GCP uses `labels`, not `tags`)

## Standard Variables (GCP)
- `prefix` — resource name prefix (e.g., `acme-uc1-dev`)
- `project` — GCP project ID
- `region` — GCP region (default: `us-central1`)
- `labels` — additional labels (`map(string)`)
- `env_default_labels` — default labels from environment layer
- `network` — VPC network name (where applicable)
- `subnetwork` — subnetwork name (where applicable)

## Naming Pattern
```hcl
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, {max_length})
```
<!-- Examples: GCS bucket uses 'gcs' (max 63), Cloud Run uses 'run' (max 49).
     Note: GCS buckets use `location` not `region`; Cloud Run and Cloud SQL use `region`. -->

## Variable Conventions
- Use `optional(type, default)` syntax (Terraform 1.3+) for object attributes
- Complex descriptions use `<<-EOT` heredoc format
- All variables need `type`, `description`, and sensible `default` where possible

## Provider Versions
```hcl
google = { source = "hashicorp/google", version = ">=5.0,<6.0" }
```

## IAM & Security
- Use service accounts for identity-based access — never service account key files
- Prefer Workload Identity Federation for CI/CD pipelines
- Enable CMEK (`kms_key_name`) by default where supported
- Use Private Service Connect for private connectivity to managed services
- No hardcoded secrets, project IDs, or credentials in module code
