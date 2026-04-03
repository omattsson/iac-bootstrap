# Workspace Instructions — Contoso Infrastructure Automation

## Workspace Overview

This workspace contains infrastructure-as-code for Contoso's Azure platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable Azure resource modules |
| **Orchestration** | `core-infrastructure/` | Terragrunt config for all environments |
| **Pipelines** | `iac-pipeline-templates/` | Azure DevOps pipeline templates |

## Module Source Convention

```
git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref={tag}
```

Version tags managed in `subscription.hcl` → `module_tags` local.

## Standard Variable Set (Cross-Module)

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `app-weu-dev`)
- `location` — Azure region (default: `westeurope`)
- `resource_group_name` — Target resource group
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from Terragrunt inputs
- `subscription_id`, `tenant_id` — Azure identifiers

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- Key Vault: `{prefix}-kv-{suffix}` (max 24 chars, truncated with `substr`)
- Private Endpoints: `{prefix}-pe-{suffix}`
- All names sanitized with `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Always merge environment defaults with resource-specific tags. `var.tags` wins on key conflicts.
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Terragrunt Hierarchy

```
config/{environment}/{site}/{stack}/{component}/terragrunt.hcl
```
- `subscription.hcl` → Subscription ID, module versions
- `site.hcl` → Region, location
- `stack.hcl` → Stack name, prefix
- `_envcommon/*.hcl` → Shared module configs with dependencies and inputs

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config lives in `_envcommon`, variables flow from hierarchy
3. **No hardcoded secrets** — use Key Vault, MSI, or Terragrunt inputs
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
