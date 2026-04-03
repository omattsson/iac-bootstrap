---
description: "Terraform native test conventions for Acme AWS .tftest.hcl files. Use when writing, modifying, or reviewing terraform test files using plan-only assertions and mock providers."
applyTo: "**/*.tftest.hcl"
---

# Terraform Native Test Standards (AWS)

## Required Boilerplate
Every test file must include:
```hcl
mock_provider "aws" {}
```

## All tests use `command = plan` — never `command = apply`.

## Required Variables
Include all `common.variables.tf` variables in the `variables {}` block.

```hcl
variables {
  prefix           = "test-auto"
  region           = "us-east-1"
  tags             = {}
  env_default_tags = { managed_by = "Terraform" }
  # Don't forget vpc_id and subnet_ids if the module requires them
}
```

## Organization
- One test file per feature area: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names
- Group related assertions in the same `run` block
