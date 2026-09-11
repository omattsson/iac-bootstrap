# Create Infrastructure Pipeline

Generate GitHub Actions pipeline configuration for infrastructure deployments.

## Usage
Describe the pipeline as the argument: `$ARGUMENTS`

If unclear, ask:
- Single component or full stack?
- Which environment(s)?
- Drift detection needed?
- Destroy pipeline needed?

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan** — runs always, publishes plan artifact
2. **Apply** — runs on protected branches only, requires approval

## Templates

### Single Component Pipeline

name: plan-apply-{component}
on:
  push:
    branches: [main]
    paths:
      - 'infrastructure-config/**/{component}/**'
  pull_request:
    paths:
      - 'infrastructure-config/**/{component}/**'

jobs:
  plan:
    uses: acme/pipeline-templates/.github/workflows/tf-plan.yml@main
    with:
      working_directory: infrastructure-config/dev/platform/{component}
    permissions:
      id-token: write
      contents: read
  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    uses: acme/pipeline-templates/.github/workflows/tf-apply.yml@main
    with:
      working_directory: infrastructure-config/dev/platform/{component}
    permissions:
      id-token: write
      contents: read
    environment: production


### Stack Pipeline (all components)

name: plan-apply-stack
on:
  push:
    branches: [main]
    paths:
      - 'infrastructure-config/**'

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terragrunt run-all plan
        working-directory: infrastructure-config/dev/platform
  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    environment: production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terragrunt run-all apply -auto-approve
        working-directory: infrastructure-config/dev/platform


### Drift Detection Pipeline

name: drift-detection
on:
  schedule:
    - cron: '0 6 * * 1-5'  # Weekdays at 06:00 UTC

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: plan
        run: terragrunt run-all plan --detailed-exitcode
        working-directory: infrastructure-config
        continue-on-error: true
      - name: Notify on drift
        if: steps.plan.outcome == 'failure'
        run: echo 'Drift detected — review plan output'


### Destroy Pipeline

name: destroy-{component}
on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        type: choice
        options: [dev, staging, prod]
      component:
        description: 'Component to destroy'
        required: true
      confirm:
        description: 'Type DESTROY to confirm'
        required: true

jobs:
  plan-destroy:
    if: github.event.inputs.confirm == 'DESTROY'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terragrunt run-all plan -destroy
        working-directory: infrastructure-config/${{ github.event.inputs.environment }}/platform/${{ github.event.inputs.component }}
  destroy:
    needs: plan-destroy
    environment: ${{ github.event.inputs.environment }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: terragrunt run-all apply -destroy -auto-approve
        working-directory: infrastructure-config/${{ github.event.inputs.environment }}/platform/${{ github.event.inputs.component }}


## Authentication

Managed Identity / OIDC

## Standard Parameters

- `environment` — target environment name
- `working_directory` — path to component/stack root
- `terraform_version` — Terraform version to use

## Conventions

- Name: `{action}-{component}.yml` (e.g. `deploy-networking.yml`)
- Two-stage: plan (on PR) → apply (on merge to main, with environment protection)
- Use `concurrency:` to prevent parallel runs on the same stack
