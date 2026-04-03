# Create Infrastructure Pipeline

Generate Azure DevOps pipeline configuration for infrastructure deployments.

## Usage
Describe the pipeline as the argument: `$ARGUMENTS`

If unclear, ask:
- Single component or full stack?
- Which environment(s)?
- Drift detection needed?

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan** — runs always, publishes plan artifact
2. **Apply** — runs on protected branches only, requires approval

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

### Drift Detection Pipeline
```yaml
schedules:
  - cron: '0 6 * * 1-5'
    displayName: 'Weekday drift check'
    branches:
      include: [main]
    always: true

extends:
  template: terragrunt/plan_only.yml@templates
  parameters:
    deployment_environment: '{environment}'
    project: '{component}'
    pool_name: 'infra-agents'
    notify_on_drift: true
```

## Authentication
- `ARM.USE.MSI = true`
- `ARM.USE.AZUREAD = true`
- `az login --identity`

## Conventions
- One pipeline per component per environment
- Use template repo for shared stages
- Lock timeout: `-lock-timeout=20m`
