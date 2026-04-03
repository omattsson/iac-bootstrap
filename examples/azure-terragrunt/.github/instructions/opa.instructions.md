---
description: "OPA/Rego policy-as-code conventions for Contoso Azure infrastructure. Use when writing, modifying, or reviewing Rego policies that evaluate Terraform plan JSON for Contoso compliance and governance."
applyTo: "policies/**/*.rego,policies/**/*_test.rego"
---

# OPA/Rego Policy Standards

## When to Use OPA/Rego
Use OPA policies for **plan-time governance** evaluated against `terraform show -json` output:
- Enforce Contoso policies across all modules from one place
- Gate plan approval in Azure DevOps pipelines
- Evaluate cross-resource relationships (e.g., private endpoint required if public access disabled)
- Policy logic that needs version-controlled, peer-reviewed rules

## Policy Layout

```
policies/
  contoso/
    naming.rego            ← naming convention checks
    naming_test.rego
    tags.rego              ← required tag checks
    tags_test.rego
    network.rego           ← network hardening checks
    network_test.rego
  data/
    required_tags.json     ← list of required tag keys
    allowed_regions.json   ← approved Azure regions
```

## Policy Boilerplate

```rego
package contoso.tags

import rego.v1

required_tags := {"environment", "product", "managed_by"}

violations contains msg if {
    some resource in input.resource_changes
    resource.change.actions[_] in {"create", "update"}
    some tag in required_tags
    not resource.change.after.tags[tag]
    msg := sprintf("Resource %s is missing required tag '%s'", [resource.address, tag])
}
```

## Evaluating Policies Against an Azure DevOps Plan

```bash
# In the pipeline plan stage
terraform plan -out=tfplan.binary
terraform show -json tfplan.binary > tfplan.json

# Evaluate policies
opa eval \
  --input tfplan.json \
  --data policies/ \
  --fail-defined \
  "data.contoso.tags.violations"
```

## Policy Test Boilerplate

```rego
package contoso.tags_test

import rego.v1

# --- passing case: all required tags present ---
test_no_violation_when_all_tags_present if {
    count(violations) == 0 with input as {
        "resource_changes": [{
            "address": "azurerm_key_vault.default",
            "type": "azurerm_key_vault",
            "change": {
                "actions": ["create"],
                "after": {
                    "tags": {
                        "environment": "dev",
                        "product":     "platform",
                        "managed_by":  "Terraform"
                    }
                }
            }
        }]
    }
}

# --- failing case: missing environment tag ---
test_violation_when_environment_tag_missing if {
    count(violations) > 0 with input as {
        "resource_changes": [{
            "address": "azurerm_key_vault.default",
            "type": "azurerm_key_vault",
            "change": {
                "actions": ["create"],
                "after": {
                    "tags": {
                        "product":    "platform",
                        "managed_by": "Terraform"
                    }
                }
            }
        }]
    }
}
```

## Running Policy Tests
```bash
# Run all Contoso policy tests
opa test policies/ -v

# Run tests for a specific package
opa test policies/contoso/ -v --run tags
```

## Azure DevOps Pipeline Integration
```yaml
- task: Bash@3
  displayName: 'Evaluate OPA governance policies'
  inputs:
    targetType: inline
    script: |
      terraform show -json $(Pipeline.Workspace)/tfplan.binary > tfplan.json
      opa eval \
        --input tfplan.json \
        --data policies/ \
        --fail-defined \
        "data.contoso.main.violations"
```

## Package Conventions
| Package | Purpose |
|---------|---------|
| `contoso.tags` | Required tag enforcement |
| `contoso.naming` | Naming pattern enforcement |
| `contoso.network` | Network hardening (public access, private endpoints) |
| `contoso.iam` | Identity and access management rules |
