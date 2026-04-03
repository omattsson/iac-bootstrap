# Create Terraform Module

Scaffold a new `tf-module-{name}` directory following Contoso conventions.

## Usage
Provide the module name as the argument: `$ARGUMENTS`

If no name is given, ask for:
- Module name (lowercase, hyphenated)
- Primary Azure resource type(s)
- Optional features: private endpoints, diagnostic settings, RBAC toggles

## Directory Structure

```
tf-module-{name}/
├── main.tf                    # Provider requirements + data sources
├── {resource}.tf              # Core resource(s)
├── locals.tf                  # Name construction, tag merging
├── variables.tf               # Module-specific variables
├── common.variables.tf        # Standard cross-module variables
├── outputs.tf                 # Module outputs
├── versions.tf                # Version constraints
├── README.md
├── .pre-commit-config.yaml
├── .tflint.hcl
├── .terraform-docs.yml
├── examples/
│   └── basic/
│       ├── main.tf
│       └── variables.tf
└── tests/
    └── {resource}.tftest.hcl
```

## File Templates

### versions.tf
```hcl
terraform {
  required_version = ">=1.3"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">=4.21.0,<5.0"
    }
  }
}
```

### locals.tf
```hcl
locals {
  name_suffix = replace(var.suffix, "/[^0-9A-Za-z]+/", "-")
  name        = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, 24)
  tags        = merge(var.env_default_tags, var.tags)
}
```

### Resource file
```hcl
resource "azurerm_{resource}" "default" {
  name                = local.name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = local.tags
}
```

### outputs.tf
```hcl
output "name" {
  value       = azurerm_{resource}.default.name
  description = "Name of the resource."
}

output "id" {
  value       = azurerm_{resource}.default.id
  description = "The ID of the resource."
}
```

## Post-Creation
```bash
cd tf-module-{name}
terraform fmt -recursive
terraform validate
terraform test
```
