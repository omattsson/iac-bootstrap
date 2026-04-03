# Create Infrastructure Pipeline

Generate GitHub Actions workflow configuration for infrastructure deployments.

## Usage
Describe the pipeline as the argument: `$ARGUMENTS`

If unclear, ask:
- Single component or full stack?
- Which environment(s)?
- Drift detection needed?
- Destroy workflow needed?

## Pipeline Architecture

All pipelines follow a two-stage flow:
1. **Plan** — runs always, publishes plan artifact
2. **Apply** — runs on protected branches only, requires environment approval

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

### Multi-Stack Pipeline
```yaml
name: 'Terraform Stack — {environment}'

on:
  push:
    branches: [main]
    paths: ['config/{environment}/**']

permissions:
  id-token: write
  contents: read

jobs:
  plan-all:
    name: Plan All
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-plan
          aws-region: us-east-1
      - name: Terragrunt Plan All
        working-directory: config/{environment}
        run: terragrunt run-all plan -lock-timeout=20m

  apply-all:
    name: Apply All
    needs: plan-all
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: {environment}-approval
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-apply
          aws-region: us-east-1
      - name: Terragrunt Apply All
        working-directory: config/{environment}
        run: terragrunt run-all apply --terragrunt-non-interactive -lock-timeout=20m
```

### Drift Detection Pipeline
```yaml
name: 'Drift Detection — {environment}'

on:
  schedule:
    - cron: '0 6 * * 1-5'   # Weekdays at 06:00 UTC
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  drift-check:
    name: Drift Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-plan
          aws-region: us-east-1
      - name: Terragrunt Plan (drift check)
        working-directory: config/{environment}
        run: |
          terragrunt run-all plan -detailed-exitcode -lock-timeout=20m
        continue-on-error: true
      - name: Notify on drift
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          payload: '{"text":"⚠️ Infrastructure drift detected in {environment}"}'
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Destroy Pipeline
```yaml
name: 'Terraform Destroy — {component} — {environment}'

on:
  workflow_dispatch:
    inputs:
      component:
        description: 'Component path to destroy'
        required: true
      confirm:
        description: 'Type DESTROY to confirm'
        required: true

permissions:
  id-token: write
  contents: read

jobs:
  destroy:
    name: Destroy
    runs-on: ubuntu-latest
    environment: {environment}-destroy-approval
    if: github.event.inputs.confirm == 'DESTROY'
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::${{ vars.AWS_ACCOUNT_ID }}:role/terraform-apply
          aws-region: us-east-1
      - name: Terragrunt Destroy
        working-directory: ${{ github.event.inputs.component }}
        run: terragrunt destroy --terragrunt-non-interactive -lock-timeout=20m
```

## Authentication
- OIDC via `aws-actions/configure-aws-credentials@v4`
- Separate IAM roles for plan (`terraform-plan`) and apply (`terraform-apply`)
- No long-lived AWS credentials — all auth via GitHub OIDC provider

## Conventions
- Environment approval via GitHub Environment protection rules
- One workflow file per component per environment
- Artifact retention: 1 day for plan files
- Lock timeout: `-lock-timeout=20m`
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in runner
