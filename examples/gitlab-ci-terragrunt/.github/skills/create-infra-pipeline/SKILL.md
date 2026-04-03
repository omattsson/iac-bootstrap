---
name: create-infra-pipeline
description: "Generate GitLab CI pipeline YAML for Terraform/Terragrunt deployments. Use when: creating CI/CD pipelines for infrastructure, adding plan/apply stages, configuring drift detection, setting up destroy pipelines."
---

# Create Infrastructure Pipeline

Generates GitLab CI pipeline configuration for infrastructure deployments.

## When to Use
- Creating a new deployment pipeline for a component or stack
- Setting up drift detection on a schedule
- Configuring plan→apply flow with manual approval gates
- Adding a manual destroy pipeline

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan stage** — runs always, publishes plan artifact
2. **Apply stage** — `when: manual` on protected branches only

## Templates

### Single Component Pipeline
```yaml
# ci/{component}-{environment}.gitlab-ci.yml

include:
  - local: ci/terraform-base.gitlab-ci.yml

variables:
  TF_ROOT: config/{environment}/{site}/{stack}/{component}
  ENVIRONMENT: {environment}

stages:
  - plan
  - apply

plan:{component}:
  stage: plan
  extends: .terraform:plan
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

apply:{component}:
  stage: apply
  extends: .terraform:apply
  needs: ["plan:{component}"]
  when: manual
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  environment:
    name: {environment}
```

### Base Job Templates (`ci/terraform-base.gitlab-ci.yml`)
```yaml
.terraform:plan:
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal
        -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$TF_ROOT"
    - terragrunt init -lock-timeout=20m
    - terragrunt plan -out=tfplan -lock-timeout=20m
  artifacts:
    paths: ["$TF_ROOT/tfplan"]
    expire_in: 1 day

.terraform:apply:
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal
        -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd "$TF_ROOT"
    - terragrunt apply -lock-timeout=20m tfplan
```

### Drift Detection Pipeline
```yaml
# ci/drift-{environment}.gitlab-ci.yml

stages:
  - drift

drift:{environment}:
  stage: drift
  image: ghcr.io/gruntwork-io/terragrunt:latest
  id_tokens:
    AZURE_TOKEN:
      aud: api://AzureADTokenExchange
  before_script:
    - az login --federated-token "$AZURE_TOKEN" --service-principal
        -u "$AZURE_CLIENT_ID" --tenant "$AZURE_TENANT_ID"
  script:
    - cd config/{environment}
    - terragrunt run-all plan -detailed-exitcode -lock-timeout=20m
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Schedule in GitLab: Project → CI/CD → Schedules → `0 6 * * 1-5` on `main`.

## Authentication
- Workload Identity Federation via GitLab `id_tokens` and `az login --federated-token`
- No client secrets — federated credentials only
- CI/CD variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` (group-level, masked)

## Conventions
- Shared job templates in `ci/terraform-base.gitlab-ci.yml`, included from root `.gitlab-ci.yml`
- Always `when: manual` for apply stage — no auto-deploy
- Lock timeout: `-lock-timeout=20m`
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in job
