---
description: "GitHub Actions pipeline standards for Acme GCP IaC deployments. Use when creating or modifying pipeline config for Terraform plan, apply, or drift detection."
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Actions Pipeline Standards (GCP)

## Two-Stage Pattern
All deployment pipelines: Plan stage → Apply stage (on protected branches with approval).

## Authentication
- Use Workload Identity Federation with GitHub Actions — no service account key files
- Service account impersonated via `google-github-actions/auth@v2` with OIDC token
- Use separate service accounts per environment: `github-actions-{env}@acme-{env}-{id}.iam.gserviceaccount.com`
- Workload Identity Pool scoped to specific repo and branch

## Provider Caching
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.terraform.d/plugin-cache
    key: terraform-providers-${{ hashFiles('**/.terraform.lock.hcl') }}
```

## Standard Parameters
- `environment` — target environment (dev, staging, prod)
- `working_directory` — Terraform root module path
- `gcp_project` — GCP project ID
- `gcp_region` — GCP region (default: us-central1)

## Conventions
- Plan artifacts saved and reused in apply stage — never re-plan during apply
- Lock timeout: `-lock-timeout=20m` for shared state
- Drift detection: scheduled plan-only workflow on `main` branch
- GCS backend for all environments. Separate state bucket per environment.
