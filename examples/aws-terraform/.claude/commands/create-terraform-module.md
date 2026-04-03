# Create Terraform Module

Scaffold a new `tf-module-{name}` directory following Acme conventions.

## Usage
Provide the module name as the argument: `$ARGUMENTS`

If no name is given, ask for:
- Module name (lowercase, hyphenated)
- Primary AWS resource type(s)
- Optional features: VPC endpoints, KMS encryption, IAM policy toggles

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
    aws = {
      source  = "hashicorp/aws"
      version = ">=5.0,<6.0"
    }
  }
}
```

### locals.tf
```hcl
locals {
  name_suffix = lower(regexreplace(var.suffix, "[^0-9a-zA-Z]+", "-"))
  name        = var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}"
  tags        = merge(var.env_default_tags, var.tags)
}
```

### Resource file
```hcl
resource "aws_{resource}" "default" {
  name = local.name
  tags = local.tags
}
```

### outputs.tf
```hcl
output "name" {
  value       = aws_{resource}.default.name
  description = "Name of the resource."
}

output "arn" {
  value       = aws_{resource}.default.arn
  description = "The ARN of the resource."
}

output "id" {
  value       = aws_{resource}.default.id
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
