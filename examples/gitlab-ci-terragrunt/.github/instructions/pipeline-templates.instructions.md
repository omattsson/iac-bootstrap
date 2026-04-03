---
description: "GitLab CI pipeline standards for IaC deployments. Use when creating or modifying pipeline YAML for Terraform/Terragrunt plan, apply, destroy, or drift detection."
applyTo: "{.gitlab-ci.yml,ci/**/*.yml}"
---

# GitLab CI Pipeline Standards

## Two-Stage Pattern
All deployment pipelines: Plan stage → Apply stage (`when: manual` on protected branches).

## Authentication
- Workload Identity Federation via GitLab `id_tokens` (OIDC)
- `az login --federated-token "$AZURE_TOKEN" --service-principal`
- No client secrets — always use federated credentials
- Variables `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` set at group level (masked)

## Template/Reuse Pattern
- Shared job templates in `ci/terraform-base.gitlab-ci.yml`
- Component pipelines use `include: - local: ci/terraform-base.gitlab-ci.yml`
- Extend base jobs with `extends: .terraform:plan` / `extends: .terraform:apply`

## Conventions
- Apply stage always `when: manual` — no automatic deploys
- Lock timeout: `-lock-timeout=20m`
- Plan artifact expires in 1 day
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in job or runner config
