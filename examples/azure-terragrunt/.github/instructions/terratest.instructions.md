---
description: "Terratest (Go) integration test conventions for Azure modules. Use when writing, modifying, or reviewing Go-based integration tests that deploy real Azure resources to validate module behavior end-to-end."
applyTo: "tests/integration/**/*_test.go"
---

# Terratest Integration Test Standards

## When to Use Terratest
Use Terratest for integration tests that **require real Azure resources**:
- Validating actual resource creation, configuration, and networking
- Testing Azure provider behavior that mock providers cannot simulate
- End-to-end smoke tests run in non-production Azure subscriptions

Prefer native `.tftest.hcl` (plan-only) for unit-style assertions. Use Terratest only when plan-only coverage is insufficient.

## Test File Layout

```
tests/
  integration/
    {module}_test.go     ← one file per module or scenario
    go.mod
    go.sum
```

## Required Boilerplate

```go
package test

import (
    "os"
    "testing"

    "github.com/gruntwork-io/terratest/modules/terraform"
    "github.com/stretchr/testify/assert"
)

func TestKeyVault(t *testing.T) {
    t.Parallel()

    opts := &terraform.Options{
        TerraformDir: "../../",
        Vars: map[string]interface{}{
            "prefix":              "test-auto",
            "location":            "westeurope",
            "resource_group_name": os.Getenv("TF_VAR_resource_group_name"),
            "tags":                map[string]string{"managed_by": "terratest"},
            "env_default_tags":    map[string]string{"environment": "test"},
        },
    }

    defer terraform.Destroy(t, opts)
    terraform.InitAndApply(t, opts)

    // Assertions
    resourceName := terraform.Output(t, opts, "name")
    assert.NotEmpty(t, resourceName)

    resourceID := terraform.Output(t, opts, "id")
    assert.NotEmpty(t, resourceID)
}
```

## Conventions

- Always call `defer terraform.Destroy(t, opts)` **before** `InitAndApply` — ensures cleanup even on test failure
- Run tests in isolated resource groups; never share state between test runs
- Use `t.Parallel()` unless tests share resources
- Assert specific output values with `terraform.Output(t, opts, "output_name")`
- Use `os.Getenv` for sensitive inputs (subscription IDs, credentials) — never hardcode
- Inject Azure credentials via environment variables:
  - `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`

## Tag All Test Resources
```go
"tags": map[string]string{
    "managed_by":  "terratest",
    "environment": "test",
    "product":     "automated-test",
},
```
Enables easy cleanup via Azure tag-based queries.

## CI Considerations
- Terratest runs in a dedicated integration test pipeline stage, **not** on every PR
- Requires Azure credentials injected as pipeline variables (ADO secret variables)
- Tag all test resources with `managed_by = "terratest"` for cleanup identification
- Use a dedicated test subscription or resource group with an expiry policy
