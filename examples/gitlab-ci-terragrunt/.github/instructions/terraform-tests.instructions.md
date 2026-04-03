---
description: "Terraform native test conventions for .tftest.hcl files. Use when writing, modifying, or reviewing terraform test files using plan-only assertions and mock providers."
applyTo: "**/*.tftest.hcl"
---

# Terraform Native Test Standards

## Required Boilerplate
Every test file must include:
```hcl
mock_provider "azurerm" {}

override_data {
  target = data.azurerm_subscription.current
  values = { tenant_id = "00000000-0000-0000-0000-000000000000" }
}

variables {
  prefix              = "test-auto"
  location            = "westeurope"
  resource_group_name = "test-rg"
  tags                = {}
  env_default_tags    = { managed_by = "Terraform" }
}
```

## All tests use `command = plan` — never `command = apply`.

## Required Variables
Include all `common.variables.tf` variables in the `variables {}` block.

## Organization
- One test file per feature area: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names
- Group related assertions in the same `run` block
