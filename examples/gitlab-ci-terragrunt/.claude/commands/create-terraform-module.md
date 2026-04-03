---
name: create-terraform-module
description: "Create a new reusable Terraform module following Globex conventions. Use when: scaffolding a new tf-module-* repo, adding Azure resource modules, creating module boilerplate."
---

# Create Terraform Module

Scaffolds a new `tf-module-{name}` directory following workspace conventions.

## When to Use
- Creating a new Azure resource module from scratch
- Generating boilerplate for a new module repo

## Prerequisites
- Module name (lowercase, hyphenated)
- Primary Azure resource type(s)
- Optional features needed (private endpoints, diagnostic settings, RBAC toggles)

## Procedure

### 1. Create Directory Structure
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
├── examples/
│   └── basic/
│       ├── main.tf
│       └── variables.tf
└── tests/
    └── {resource}.tftest.hcl
```

### 2. File Templates

#### versions.tf
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

#### locals.tf
```hcl
locals {
  name_suffix = replace(var.suffix, "/[^0-9A-Za-z]+/", "-")
  name        = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, 24)
  tags        = merge(var.env_default_tags, var.tags)
}
```

### 3. Post-Creation
```bash
terraform fmt -recursive
terraform validate
terraform test
```
