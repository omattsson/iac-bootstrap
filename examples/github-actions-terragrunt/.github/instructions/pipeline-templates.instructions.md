---
description: "GitHub Actions pipeline standards for IaC deployments. Use when creating or modifying workflow YAML for Terraform/Terragrunt plan, apply, destroy, or drift detection."
applyTo: ".github/workflows/*.yml"
---

# GitHub Actions Pipeline Standards

## Two-Stage Pattern
All deployment pipelines: Plan job → Apply job (on `main` branch with environment approval gate).

## Authentication
- OIDC via `aws-actions/configure-aws-credentials@v4`
- Separate IAM roles for plan (`terraform-plan`) and apply (`terraform-apply`)
- Always set `permissions: id-token: write` at workflow level

## Environment Approval
- Use GitHub Environments for approval gates (`environment: {env}-approval`)
- Configure required reviewers in environment protection rules
- Apply job always has `if: github.ref == 'refs/heads/main'`

## Conventions
- One workflow file per component per environment
- Lock timeout: `-lock-timeout=20m`
- Provider caching: set `TF_PLUGIN_CACHE_DIR` in runner environment
- Upload plan artifact; download in apply job
