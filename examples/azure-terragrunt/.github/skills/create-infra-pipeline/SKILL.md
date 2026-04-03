---
name: create-infra-pipeline
description: "Generate Azure DevOps pipeline YAML for Terraform/Terragrunt deployments. Use when: creating CI/CD pipelines for infrastructure, adding plan/apply stages, configuring drift detection, adding approval gates, setting up a destroy pipeline."
---

# Create Infrastructure Pipeline

Generates Azure DevOps pipeline configuration for infrastructure deployments.

## When to Use
- Creating a new deployment pipeline for a component or stack
- Setting up drift detection
- Configuring plan→apply flow with approval gates

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan stage** — runs always, publishes plan artifact
2. **Apply stage** — runs on protected branches only, requires approval

## Templates

### Single Component Pipeline
```yaml
trigger:
  branches:
    include: [development, main]
  paths:
    include: ['{environment}/{component}']

resources:
  repositories:
    - repository: templates
      type: git
      name: contoso/iac-pipeline-templates
      ref: refs/heads/main

extends:
  template: terragrunt/plan_apply.yml@templates
  parameters:
    deployment_environment: '{environment}'
    project: '{component}'
    pool_name: 'infra-agents'
    approval_environment: '{environment}-approval'
```

### Drift Detection
```yaml
schedules:
  - cron: '0 6 * * 1-5'
    displayName: 'Weekday drift check'
    branches:
      include: [main]
    always: true
```

## Authentication
- `ARM.USE.MSI = true`
- `ARM.USE.AZUREAD = true`

## Conventions
- One pipeline per component per environment
- Use template repo for shared stages
- Lock timeout: `-lock-timeout=20m`
