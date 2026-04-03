---
description: "Terraform native test conventions for Acme GCP .tftest.hcl files. Use when writing, modifying, or reviewing terraform test files using plan-only assertions and mock providers."
applyTo: "**/*.tftest.hcl"
---

# Terraform Native Test Standards (GCP)

## Required Boilerplate
Every test file must include:
```hcl
mock_provider "google" {}
```

## All tests use `command = plan` — never `command = apply`.

## Required Variables
Include all `common.variables.tf` variables in the `variables {}` block.

```hcl
variables {
  prefix             = "test-auto"
  project            = "acme-test-000000"
  region             = "us-central1"
  labels             = {}
  env_default_labels = { managed_by = "terraform" }
  # Don't forget network and subnetwork if the module requires them
}
```

## Organization
- One test file per feature area: `naming.tftest.hcl`, `labels.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names
- Group related assertions in the same `run` block
