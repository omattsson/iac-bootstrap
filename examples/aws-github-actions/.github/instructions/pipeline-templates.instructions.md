---
description: "GitHub Actions pipeline standards for Acme AWS IaC deployments. Use when creating or modifying pipeline config for Terraform plan, apply, or drift detection."
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Actions Pipeline Standards (AWS)

## Two-Stage Pattern
All deployment pipelines: Plan stage → Apply stage (on protected branches with approval).

## Authentication
- Use OIDC with GitHub Actions — no long-lived AWS access keys
- IAM role assumed via `aws-actions/configure-aws-credentials@v4` with OIDC token
- Use separate IAM roles per environment: `arn:aws:iam::{account_id}:role/github-actions-{env}`
- Trust policy scoped to specific repo and branch

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
- `aws_region` — AWS region (default: us-east-1)

## Conventions
- Plan artifacts saved and reused in apply stage — never re-plan during apply
- Lock timeout: `-lock-timeout=20m` for shared state
- Drift detection: scheduled plan-only workflow on `main` branch
