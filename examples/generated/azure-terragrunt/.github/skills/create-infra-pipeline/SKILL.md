---
name: create-infra-pipeline
description: "Generate GitHub Actions pipeline config for Terraform/Terragrunt deployments. Use when: creating CI/CD pipelines for infrastructure, adding plan/apply stages, configuring drift detection, adding approval gates, setting up a destroy pipeline."
---

# Create Infrastructure Pipeline

Generates GitHub Actions pipeline configuration for infrastructure deployments.

## When to Use
- Creating a new deployment pipeline for a component or stack
- Setting up drift detection with notifications
- Configuring plan→apply flow with approval gates

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan stage** — runs always, publishes plan artifact
2. **Apply stage** — runs on protected branches only, requires approval

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

<!-- Azure DevOps example:
```yaml
trigger:
  branches:
    include: [development, main]
  paths:
    include: [{environment}/{component}]

resources:
  repositories:
    - repository: templates
      type: git
      name: acme/github.com/acme/pipeline-templates
      ref: refs/heads/main

extends:
  template: terraform_apply_template.yml@templates
  parameters:
    deployment_environment: '{environment}'
    project: '{component}'
    pool_name: '{pool_name}'
    approval_environment: '{approval_environment}'
```
-->
<!-- GitHub Actions example:
```yaml
name: 'Terraform {component}'
on:
  push:
    branches: [main]
    paths: ['{environment}/{component}/**']
  pull_request:
    paths: ['{environment}/{component}/**']

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
      - run: terraform plan -out=tfplan
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan
          path: tfplan

  apply:
    needs: plan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: {approval_environment}
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: actions/download-artifact@v4
      - run: terraform apply tfplan
```
-->

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
      - run: terragrunt run-all plan --detailed-exitcode
        working-directory: infrastructure-config
        continue-on-error: true
      - name: Notify on drift
        if: failure()
        run: echo 'Drift detected — review plan output'


## Authentication

Managed Identity / OIDC
<!-- Example Azure MSI:
- ARM.USE.MSI = true
- ARM.USE.AZUREAD = true
- az login --identity
-->
<!-- Example AWS OIDC:
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::ACCOUNT:role/terraform
-->
<!-- Example GCP Workload Identity:
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/PROJECT/locations/global/...
-->

## Standard Parameters

- `environment` — target environment name
- `working_directory` — path to component/stack root
- `terraform_version` — Terraform version to use

## Conventions
- Name: `{action}-{component}.yml` (e.g. `deploy-networking.yml`)
- Two-stage: plan (on PR) → apply (on merge to main, with environment protection)
- Use `concurrency:` to prevent parallel runs on the same stack
