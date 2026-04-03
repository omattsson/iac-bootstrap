---
description: "Terraform coding standards for Globex Azure modules. Use when writing or modifying .tf files including resources, variables, outputs, locals, and provider configurations."
applyTo: "tf-module-*/**/*.tf"
---

# Terraform Module Standards

## File Organization
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by Azure resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs
- `versions.tf` — terraform and provider version constraints

## Resource Conventions
- All single resources use identifier `"default"` (e.g., `azurerm_key_vault.default`)
- Map-driven resources use `for_each` with descriptive keys
- Use `count` for boolean on/off features
- Tags: `local.tags = merge(var.env_default_tags, var.tags)` — always

## Naming Pattern
```hcl
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-kv-${local.name_suffix}", 0, 24)
```

## Variable Conventions
- Use `optional(type, default)` syntax (Terraform 1.3+) for object attributes
- Complex descriptions use `<<-EOT` heredoc format
- All variables need `type`, `description`, and sensible `default` where possible

## Provider Versions
```hcl
azurerm = { source = "hashicorp/azurerm", version = ">=4.21.0,<5.0" }
```

## No hardcoded secrets, subscription IDs, or credentials in module code.
