# Workspace Instructions — Contoso Infrastructure Automation

## Workspace Overview

This workspace contains infrastructure-as-code for Contoso's Azure platform.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable Azure resource modules |
| **Orchestration** | `infrastructure-config/` | Terragrunt config for all environments |
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

## Module Maintenance & Backward Compatibility

### Adding optional variables (non-breaking)
Always provide a default that preserves existing behavior. Use `optional()` for new object attributes:

```hcl
# New simple variable — default keeps existing behavior for all current callers
variable "enable_purge_protection" {
  type        = bool
  default     = false
  description = "Enable soft-delete purge protection on the Key Vault."
}

# New attribute on existing object — optional() so no caller needs to change
variable "network_config" {
  type = object({
    public_access         = optional(bool, false)
    allowed_cidrs         = optional(list(string), [])
    bypass_azure_services = optional(bool, false)  # added in v1.4.0
  })
  default = {}
}
```

### Deprecating variables
Keep the old variable, add a `DEPRECATED` description, and resolve both in `locals`:

```hcl
variable "vault_sku" {
  type        = string
  default     = null
  description = "DEPRECATED: use `sku_name` instead. Will be removed in v3.0."
}

variable "sku_name" {
  type        = string
  default     = "standard"
  description = "SKU name for the Key Vault (standard or premium)."
}

locals {
  resolved_sku = var.vault_sku != null ? var.vault_sku : var.sku_name
}
```

### Renaming resources with `moved` blocks
Add a `moved` block in the same commit as any resource or `for_each` key rename. Prevents destroy/re-create:

```hcl
moved {
  from = azurerm_key_vault.kv
  to   = azurerm_key_vault.default
}

moved {
  from = azurerm_private_endpoint.default["blob"]
  to   = azurerm_private_endpoint.default["blob_endpoint"]
}
```

### Semantic versioning

| Change | Version bump | Example |
|--------|-------------|---------|
| Bug fix, doc update | Patch (`x.y.Z`) | `v1.2.3 → v1.2.4` |
| New optional variable, new output | Minor (`x.Y.0`) | `v1.2.3 → v1.3.0` |
| Removed/renamed variable, changed output type | Major (`X.0.0`) | `v1.2.3 → v2.0.0` |

Version tags pinned in `subscription.hcl`. Roll out: dev → staging → prod.

### Major version migration guides
Add `MIGRATION.md` at the module repo root for every major bump. Cover: what broke, old vs new usage, and step-by-step instructions.

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config lives in `_envcommon`, variables flow from hierarchy
3. **No hardcoded secrets** — use Key Vault, MSI, or Terragrunt inputs
4. **Plan-only tests** — Terraform native tests use `command = plan` with mock providers
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
