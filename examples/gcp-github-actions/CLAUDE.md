# CloudCo Infrastructure Automation

You are working in an infrastructure-as-code workspace for CloudCo's GCP platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable GCP resource modules |
| **Orchestration** | `infrastructure-live/` | Terragrunt config for all environments |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

```
git::https://github.com/cloudco/tf-module-{name}.git?ref={tag}
```

Version tags managed in `project.hcl` → `module_tags` local.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `cloudco-ew1-dev`)
- `project_id` — GCP project ID
- `region` — GCP region (default: `europe-west1`)
- `labels` — Additional resource labels (`map(string)`)
- `env_default_labels` — Default labels from Terragrunt inputs

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- GCS Buckets: `{prefix}-gcs-{suffix}` (globally unique, max 63 chars)
- All names sanitized: `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Labeling Standard

```hcl
local.labels = merge(var.env_default_labels, var.labels)
```
Required labels: `environment`, `product`, `managed_by = "terraform"`.

> Note: GCP uses `labels`, not `tags`. The pattern is identical but the attribute name differs.

## Environment Hierarchy

```
infrastructure-live/
├── terragrunt.hcl              # root config
└── {project}/
    ├── project.hcl             # project ID, module versions
    └── {region}/
        ├── region.hcl          # region config
        └── {stack}/
            └── {component}/
                └── terragrunt.hcl
```

Hierarchy files:
- `project.hcl` → GCP project ID, module versions
- `region.hcl` → Region
- `stack.hcl` → Stack name, prefix
- `_envcommon/*.hcl` → Shared module configs

---

## Coding Standards

### Terraform Files (`tf-module-*/**/*.tf`)

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
- Always set `project = var.project_id` explicitly

**Provider versions:**
```hcl
google = { source = "hashicorp/google", version = ">=5.0,<6.0" }
```

**No hardcoded secrets, project IDs, or credentials in module code.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "google" {}

override_data {
  target = data.google_project.current
  values = {
    project_id = "test-project-123"
    number     = 123456789
    name       = "test-project"
  }
}
```

**Standard test variables:**
```hcl
variables {
  prefix             = "test-auto"
  project_id         = "test-project-123"
  region             = "europe-west1"
  labels             = {}
  env_default_labels = { managed_by = "terraform" }
}
```

---

## Authentication & CI/CD

- **Auth:** Workload Identity Federation via `google-github-actions/auth@v2` — no service account keys
- **State:** GCS backend with state locking
- **Pipeline trigger:** Push to `main` triggers plan; manual approval triggers apply
