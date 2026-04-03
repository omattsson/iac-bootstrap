---
description: "Terraform native test conventions for .tftest.hcl files. Use when writing, modifying, or reviewing terraform test files using plan-only assertions and mock providers."
applyTo: "**/*.tftest.hcl"
---

# Terraform Native Test Standards

## Required Boilerplate
Every test file must include:
```hcl
mock_provider "aws" {}

variables {
  prefix           = "test-auto"
  region           = "us-east-1"
  tags             = {}
  env_default_tags = { managed_by = "Terraform" }
  account_id       = "123456789012"
}
```

## All tests use `command = plan` — never `command = apply`.

## Required Variables
Include all `common.variables.tf` variables in the `variables {}` block.

## Organization
- One test file per feature area: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names
- Group related assertions in the same `run` block
