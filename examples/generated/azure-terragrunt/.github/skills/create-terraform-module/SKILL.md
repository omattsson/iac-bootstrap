---
name: create-terraform-module
description: "Create a new reusable Terraform module following Acme Corp conventions. Use when: scaffolding a new tf-module-* repo, adding Azure resource modules, creating module boilerplate."
---

# Create Terraform Module

Scaffolds a new `tf-module-{name}` directory following workspace conventions.

## When to Use
- Creating a new Azure resource module from scratch
- Generating boilerplate for a new module repo
- Adding standard files (tests, examples, pre-commit) to an existing module

## Prerequisites
- Module name (lowercase, hyphenated)
- Primary Azure resource type(s)
- Optional features needed (private connectivity, diagnostics/logging, RBAC/IAM)

## Procedure

### 1. Gather Requirements
Ask for:
- Module name: used as `tf-module-{name}`
- Primary resource(s) to manage
- Optional features: private endpoints, diagnostics settings, RBAC assignments

### 2. Create Directory Structure
```
tf-module-{name}/
├── main.tf                    # Provider requirements + data sources
├── {resource}.tf              # Core resource(s)
├── locals.tf                  # Name construction, tag merging
├── variables.tf               # Module-specific variables
├── common.variables.tf       # Standard cross-module variables
├── outputs.tf                 # Module outputs
├── versions.tf                # Version constraints
├── README.md                  # Documentation
├── .pre-commit-config.yaml    # Validation hooks
├── .tflint.hcl                # TFLint rules
├── .terraform-docs.yml        # Doc generation
├── examples/
│   └── basic/
│       ├── main.tf
│       └── variables.tf
└── tests/
    └── {resource}.tftest.hcl  # Native terraform tests
```

### 3. File Templates

#### versions.tf
```hcl
terraform {
  required_version = ">=1.3"
  required_providers {
    azurerm = {
  source  = "hashicorp/azurerm"
  version = ">=4.0.0,<5.0.0"
}
  }
}
```
<!-- Example Azure:
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">=4.21.0,<5.0"
    }
-->
<!-- Example AWS:
    aws = {
      source  = "hashicorp/aws"
      version = ">=5.0,<6.0"
    }
-->

#### locals.tf — Naming Pattern
```hcl
locals {
  name = substr(
  "${var.prefix}-${local.resource_abbreviation}-${local.suffix}",
  0, 24
)
  # Tags/labels: defaults + resource-specific, resource-specific wins
  tags = merge(var.env_default_tags, var.tags)
}
```

#### Resource file pattern
```hcl
resource "azurerm_resource_group" "default" {
  name                = local.name
  location = var.location
  resource_group_name = var.resource_group_name
  tags                = local.tags

  # Resource-specific configuration...
}
```

#### outputs.tf
```hcl
output "name" {
  value       = azurerm_resource_group.default.name
  description = "Name of the resource."
}

output "id" {
  value       = azurerm_resource_group.default.id
  description = "The ID of the resource."
}
```

#### Test file pattern
```hcl
mock_provider "azurerm" {}

override_data {
  target = data.azurerm_subscription.current
  values = {
    subscription_id = "00000000-0000-0000-0000-000000000000"
    tenant_id       = "00000000-0000-0000-0000-000000000000"
  }
}

variables {
variables {
  prefix   = "test-auto"
  location = "westeurope"
}
}

run "creates_resource_with_correct_name" {
  command = plan
  assert {
    condition     = azurerm_resource_group.default.name == "test-auto-{resource_abbreviation}-mysuffix"
    error_message = "Name should follow naming convention"
  }
}

run "merges_tags_correctly" {
  command = plan
  variables {
    tags = { extra = "tag" }
  }
  assert {
    condition     = azurerm_resource_group.default.tags["extra"] == "tag"
    error_message = "Custom tags should be merged"
  }
}
```

### 4. Post-Creation
1. `terraform fmt -recursive`
2. `terraform validate`
3. `terraform test`
4. `terraform-docs` to generate README
