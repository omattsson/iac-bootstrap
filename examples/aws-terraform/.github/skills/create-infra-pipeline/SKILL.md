---
name: create-infra-pipeline
description: "Generate GitHub Actions workflow YAML for Terraform deployments. Use when: creating CI/CD pipelines for infrastructure, adding plan/apply stages, configuring drift detection."
---

# Create Infrastructure Pipeline

Generates GitHub Actions workflow configuration for infrastructure deployments.

## When to Use
- Creating a new deployment workflow for a stack or environment
- Setting up drift detection
- Configuring plan→apply flow with approval gates

## Pipeline Architecture

All workflows follow a two-stage flow:
1. **Plan job** — runs always, uploads plan artifact
2. **Apply job** — runs on protected branches only, requires environment approval

## Templates

### Single Stack Deployment Workflow
```yaml
name: 'Terraform {environment}/{stack}'

on:
  push:
    branches: [main, develop]
    paths: ['environments/{environment}/{stack}/**']
  pull_request:
    branches: [main]
    paths: ['environments/{environment}/{stack}/**']

permissions:
  id-token: write
  contents: read

env:
  TF_WORKING_DIR: environments/{environment}/{stack}
  TF_PLUGIN_CACHE_DIR: ${{ github.workspace }}/.terraform.d/plugin-cache

jobs:
  plan:
    name: Plan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1.9"
      - run: terraform init
        working-directory: ${{ env.TF_WORKING_DIR }}
      - run: terraform plan -lock-timeout=20m -out=tfplan
        working-directory: ${{ env.TF_WORKING_DIR }}
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan
          path: ${{ env.TF_WORKING_DIR }}/tfplan

  apply:
    name: Apply
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: {environment}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "~1.9"
      - run: terraform init
        working-directory: ${{ env.TF_WORKING_DIR }}
      - uses: actions/download-artifact@v4
        with:
          name: tfplan
          path: ${{ env.TF_WORKING_DIR }}
      - run: terraform apply -lock-timeout=20m tfplan
        working-directory: ${{ env.TF_WORKING_DIR }}
```

### Drift Detection Workflow
```yaml
on:
  schedule:
    - cron: '0 6 * * 1-5'

jobs:
  drift:
    name: Drift Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - uses: hashicorp/setup-terraform@v3
      - run: terraform init
        working-directory: ${{ env.TF_WORKING_DIR }}
      - run: terraform plan -detailed-exitcode -lock-timeout=20m
        working-directory: ${{ env.TF_WORKING_DIR }}
```

## Authentication
- OIDC only — never use long-lived IAM access key credentials
- IAM role ARN stored in GitHub environment variable `AWS_ROLE_ARN`
- Region stored in `AWS_REGION`

## Conventions
- One workflow per stack per environment (or use matrix strategy)
- Provider cache dir set via `TF_PLUGIN_CACHE_DIR`
- Lock timeout: `-lock-timeout=20m`
