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
  values = {
    subscription_id = "00000000-0000-0000-0000-000000000000"
    tenant_id       = "00000000-0000-0000-0000-000000000000"
  }
}
```

## All tests use `command = plan` — never `command = apply`.

## Required Variables
Include all `common.variables.tf` variables in the `variables {}` block.
Use `optional(type, default)` for object attributes (Terraform 1.3+)
<!-- Example: tf_pip must be a valid IP (e.g., "1.2.3.4"), not empty string -->

## Organization
- One test file per feature area: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names
- Group related assertions in the same `run` block
