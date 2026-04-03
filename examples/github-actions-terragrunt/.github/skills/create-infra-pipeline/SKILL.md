---
name: create-infra-pipeline
description: "Generate GitHub Actions workflow YAML for Terraform/Terragrunt deployments. Use when: creating CI/CD pipelines for infrastructure, adding plan/apply stages, configuring drift detection, setting up destroy workflows."
---

# Create Infrastructure Pipeline

Generates GitHub Actions workflow configuration for infrastructure deployments.

## When to Use
- Creating a new deployment workflow for a component or stack
- Setting up drift detection with Slack notifications
- Configuring plan→apply flow with environment protection approval gates
- Adding a manual destroy workflow

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan stage** — runs always, publishes plan artifact
2. **Apply stage** — runs on `main` only, requires GitHub Environment approval

## Templates

### Single Component Pipeline
```yaml
name: 'Terraform {component} — {environment}'

on:
  push:
    branches: [main]
    paths: ['config/{environment}/**/{component}/**']
  pull_request:
    paths: ['config/{environment}/**/{component}/**']

permissions:
  id-token: write
  contents: read

jobs:
  plan:
    name: Plan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-plan
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: '~1.9'
      - name: Install Terragrunt
        run: |
          curl -sL https://github.com/gruntwork-io/terragrunt/releases/latest/download/terragrunt_linux_amd64 -o /usr/local/bin/terragrunt
          chmod +x /usr/local/bin/terragrunt
      - name: Terragrunt Plan
        working-directory: config/{environment}/{region}/{stack}/{component}
        run: |
          terragrunt init -lock-timeout=20m
          terragrunt plan -out=tfplan -lock-timeout=20m
      - uses: actions/upload-artifact@v4
        with:
          name: tfplan-{component}-{environment}
          path: config/{environment}/{region}/{stack}/{component}/tfplan

  apply:
    name: Apply
    needs: plan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: {environment}-approval
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-apply
          aws-region: us-east-1
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: '~1.9'
      - uses: actions/download-artifact@v4
        with:
          name: tfplan-{component}-{environment}
          path: config/{environment}/{region}/{stack}/{component}
      - name: Terragrunt Apply
        working-directory: config/{environment}/{region}/{stack}/{component}
        run: terragrunt apply -lock-timeout=20m tfplan
```

### Drift Detection Pipeline
```yaml
name: 'Drift Detection — {environment}'

on:
  schedule:
    - cron: '0 6 * * 1-5'
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-plan
          aws-region: us-east-1
      - name: Drift Check
        working-directory: config/{environment}
        run: terragrunt run-all plan -detailed-exitcode -lock-timeout=20m
        continue-on-error: true
      - name: Notify on drift
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: '{"text":"⚠️ Infrastructure drift detected in {environment}"}'
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

## Authentication
- OIDC via `aws-actions/configure-aws-credentials@v4`
- Separate IAM roles: `terraform-plan` (read-only) and `terraform-apply` (write)
- No long-lived credentials — GitHub OIDC provider only

## Conventions
- One workflow file per component per environment
- Environment approval via GitHub Environment protection rules
- Lock timeout: `-lock-timeout=20m`
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in runner environment
