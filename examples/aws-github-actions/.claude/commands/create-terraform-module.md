# Create Terraform Module (AWS)

Scaffold a new `terraform-aws-{name}` directory following Acme AWS workspace conventions.

## Usage
Provide the module name as the argument: `$ARGUMENTS`

If no name is given, ask for:
- Module name (lowercase, hyphenated, e.g., `s3-bucket`, `lambda-function`)
- Primary AWS resource type(s) (e.g., `aws_s3_bucket`, `aws_lambda_function`)
- Optional features: VPC endpoints, KMS encryption, lifecycle policies, IAM role

## Directory Structure

```
terraform-aws-{name}/
├── main.tf                    # Provider requirements + data sources
├── {resource}.tf              # Core resource(s)
├── locals.tf                  # Name construction, tag merging
├── variables.tf               # Module-specific variables
├── common.variables.tf        # Standard cross-module variables
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
  name_suffix = lower(trimprefix(trimsuffix(
    replace(var.suffix, "/[^0-9A-Za-z]+/", "-"), "-"), "-"))
  name = substr(var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}", 0, {max_length})
  tags = merge(var.env_default_tags, var.tags)
}
```

### Resource file
```hcl
resource "aws_{resource_type}" "default" {
  name = local.name
  tags = local.tags
}
```

### outputs.tf
```hcl
output "name" {
  value       = aws_{resource_type}.default.name
  description = "Name of the resource."
}

output "id" {
  value       = aws_{resource_type}.default.id
  description = "The ID of the resource."
}

output "arn" {
  value       = aws_{resource_type}.default.arn
  description = "The ARN of the resource."
}
```

### Test file
```hcl
mock_provider "aws" {}

variables {
  prefix           = "test-auto"
  region           = "us-east-1"
  suffix           = "mytest"
  tags             = {}
  env_default_tags = { managed_by = "Terraform" }
}

run "creates_resource_with_correct_name" {
  command = plan
  assert {
    condition     = aws_{resource_type}.default.name == "test-auto-{abbr}-mytest"
    error_message = "Name should follow naming convention"
  }
}

run "merges_tags_correctly" {
  command = plan
  variables {
    tags = { extra = "tag" }
  }
  assert {
    condition     = aws_{resource_type}.default.tags["extra"] == "tag"
    error_message = "Custom tags should be merged"
  }
}
```

## Post-Creation

Run these commands after scaffolding:
```bash
cd terraform-aws-{name}
terraform fmt -recursive
terraform validate
terraform test
```
