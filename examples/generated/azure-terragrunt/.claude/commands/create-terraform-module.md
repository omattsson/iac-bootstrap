# Create Terraform Module

Scaffold a new `tf-module-{name}` directory following workspace conventions.

## Usage
Provide the module name as the argument: `$ARGUMENTS`

If no name is given, ask for:
- Module name (lowercase, hyphenated)
- Primary Azure resource type(s)
- Optional features: private endpoints, diagnostics settings, RBAC assignments

## Directory Structure

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

## File Templates

### versions.tf
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

### locals.tf
```hcl
locals {
  name = substr(
  "${var.prefix}-${local.resource_abbreviation}-${local.suffix}",
  0, 24
)
  tags = merge(var.env_default_tags, var.tags)
}
```

### Resource file
```hcl
resource "azurerm_key_vault" "default" {
  name                = local.name
  location = var.location
  resource_group_name = var.resource_group_name
  tags                = local.tags
}
```

### outputs.tf
```hcl
output "name" {
  value       = azurerm_key_vault.default.name
  description = "Name of the resource."
}

output "id" {
  value       = azurerm_key_vault.default.id
  description = "The ID of the resource."
}
```

### Test file
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
  prefix   = "test-auto"
  location = "westeurope"
}

run "creates_resource_with_correct_name" {
  command = plan
  assert {
    condition     = azurerm_key_vault.default.name == "test-auto-{resource_abbreviation}-mysuffix"
    error_message = "Name should follow naming convention"
  }
}

run "merges_tags_correctly" {
  command = plan
  variables {
    tags = { extra = "tag" }
  }
  assert {
    condition     = azurerm_key_vault.default.tags["extra"] == "tag"
    error_message = "Custom tags should be merged"
  }
}
```

## Post-Creation

Run these commands after scaffolding:
```bash
cd tf-module-{name}
terraform fmt -recursive
terraform validate
terraform test
```
