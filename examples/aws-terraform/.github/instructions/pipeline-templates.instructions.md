---
description: "GitHub Actions workflow standards for IaC deployments. Use when creating or modifying workflow YAML for Terraform plan, apply, or drift detection."
applyTo: ".github/workflows/*.yml"
---

# GitHub Actions Pipeline Standards

## Two-Stage Pattern
All deployment workflows: Plan job → Apply job (on protected branches with environment approval).

## Authentication
Use OIDC — never long-lived IAM access keys:
```yaml
jobs:
  terraform:
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
```

## Terraform Setup
```yaml
- uses: hashicorp/setup-terraform@v3
  with:
    terraform_version: "~1.9"
```

## Conventions
- One workflow per stack per environment (or matrix across environments)
- Plan artifact uploaded and downloaded for apply stage
- Lock timeout: `-lock-timeout=20m`
- Provider caching via `TF_PLUGIN_CACHE_DIR`
