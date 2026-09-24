---
description: "GitHub Actions pipeline standards for IaC deployments. Use when creating or modifying pipeline config for Terraform/Terragrunt plan, apply, destroy, or drift detection."
applyTo: ".github/workflows/**/*.yml"
---

# GitHub Actions Pipeline Standards

## Two-Stage Pattern
All deployment pipelines: Plan stage → Apply stage (on protected branches with approval).

## Authentication
Use OIDC federation — no long-lived secrets in workflow files.
Configure `permissions: id-token: write` and use the provider's official login action.

## Template/Reuse Pattern
Use reusable workflows (`workflow_call`) for plan/apply stages.
Reference shared templates via `uses: {org}/{repo}/.github/workflows/{template}.yml@{ref}`.

## Standard Parameters
- `environment` — target environment name
- `working_directory` — path to component/stack root
- `terraform_version` — Terraform version to use

## Conventions
- Name: `{action}-{component}.yml` (e.g. `deploy-networking.yml`)
- Two-stage: plan (on PR) → apply (on merge to main, with environment protection)
- Use `concurrency:` to prevent parallel runs on the same stack
