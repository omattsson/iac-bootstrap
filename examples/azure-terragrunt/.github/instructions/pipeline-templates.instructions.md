---
description: "Azure DevOps pipeline standards for IaC deployments. Use when creating or modifying pipeline YAML for Terraform/Terragrunt plan, apply, destroy, or drift detection."
applyTo: "**/pipelines/**/*.yml"
---

# Azure DevOps Pipeline Standards

## Two-Stage Pattern
All deployment pipelines: Plan stage → Apply stage (on protected branches with approval).

## Authentication
- `ARM.USE.MSI = true`
- `ARM.USE.AZUREAD = true`
- `az login --identity`

## Template References
Use shared templates from `contoso/iac-pipeline-templates` repo via `resources.repositories`.

## Conventions
- One pipeline per component per environment
- Lock timeout: `-lock-timeout=20m`
- Provider caching: `--provider-cache`
