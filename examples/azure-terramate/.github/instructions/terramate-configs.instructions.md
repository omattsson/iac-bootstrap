---
description: "Terramate configuration standards. Use when writing or modifying Terramate config files including stack definitions, generate_hcl blocks, and globals files."
applyTo: "infrastructure-config/**/*.tm.hcl"
---

# Terramate Configuration Standards

## Stack Definition Pattern
Every stack directory must contain a `stack.tm.hcl` file:
```hcl
stack {
  name        = "{service}-{environment}"
  description = "Manages {resource description} in {environment}"
  id          = "{service}-{environment}-{region-abbreviation}"  # Unique across workspace

  # Explicit ordering (required when stack reads outputs from another)
  after = [
    "../networking",
  ]
}
```

## Globals Pattern (`globals.tm.hcl`)
Share values across stacks using layered globals files:

Root (`infrastructure-config/globals.tm.hcl`):
```hcl
globals {
  company                = "contoso"
  state_resource_group   = "rg-tfstate-weu"
  state_storage_account  = "contosotfstateweu"

  module_versions = {
    "key-vault"     = "v2.3.0"
    "networking"    = "v1.8.0"
  }
}
```

Environment (`infrastructure-config/{env}/globals.tm.hcl`):
```hcl
globals {
  environment     = "dev"
  location        = "westeurope"
  subscription_id = "00000000-0000-0000-0000-000000000000"
}
```

Stack (`infrastructure-config/{env}/{stack}/globals.tm.hcl`):
```hcl
globals {
  prefix       = "app-weu-dev"
  service_name = "security"
}
```

## Hierarchy Files
- Root `globals.tm.hcl` — org-wide defaults: company, state backend, module versions
- Environment-level `globals.tm.hcl` — environment name, location, subscription_id
- Stack-level `globals.tm.hcl` — prefix, service name
- `stack.tm.hcl` — stack identity and `after` ordering
- `_generate/` — shared `generate_hcl` blocks (backend, provider, variables)

## Shared generate_hcl Pattern (`_generate/`)
Every shared `generate_hcl` block that creates backend/provider config lives in `_generate/`:
```hcl
generate_hcl "_generated_backend.tf" {
  content {
    terraform {
      backend "azurerm" {
        resource_group_name  = global.state_resource_group
        storage_account_name = global.state_storage_account
        container_name       = "tfstate"
        key                  = "${terramate.stack.path.relative}/terraform.tfstate"
      }
    }
  }
}
```

## Module Sources
`git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref=${global.module_versions["{name}"]}`
Version tags from root `globals.tm.hcl` → `module_versions`. Never hardcode versions in stack files.

## Cross-Stack Dependencies
- Declare ordering with `after = [...]` in `stack.tm.hcl`
- Reference outputs via `terraform_remote_state` data source in the consuming stack's `.tf` file
- Always provide a `default` value in `terraform_remote_state` for plan-time safety

## generate_hcl Rules
- Generated files are named `_generated_*.tf` and committed to the repo
- Run `terramate generate` after any change to `generate_hcl` blocks
- Never hand-edit `_generated_*.tf` files — changes will be overwritten on next generate
