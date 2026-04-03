---
description: "Terraform coding standards for Acme AWS modules. Use when writing or modifying .tf files including resources, variables, outputs, locals, and provider configurations."
applyTo: "terraform-aws-*/**/*.tf"
---

# Terraform Module Standards (AWS)

## File Organization
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by AWS resource type (e.g., `s3_bucket.tf`, `lambda_function.tf`)
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs
- `versions.tf` — terraform and provider version constraints

## Resource Conventions
- All single resources use identifier `"default"` (e.g., `aws_s3_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Use `count` for boolean on/off features
- Tags: `merge(var.env_default_tags, var.tags)` — always

## Standard Variables (AWS)
- `prefix` — resource name prefix (e.g., `acme-use1-dev`)
- `region` — AWS region (default: `us-east-1`)
- `tags` — additional tags (`map(string)`)
- `env_default_tags` — default tags from environment layer
- `vpc_id` — VPC ID (where applicable)
- `subnet_ids` — subnet IDs (where applicable)

## Naming Pattern
```hcl
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-s3-${local.name_suffix}", 0, 63)
```

## Variable Conventions
- Use `optional(type, default)` syntax (Terraform 1.3+) for object attributes
- Complex descriptions use `<<-EOT` heredoc format
- All variables need `type`, `description`, and sensible `default` where possible

## Provider Versions
```hcl
aws = { source = "hashicorp/aws", version = ">=5.0,<6.0" }
```

## IAM & Security
- Use IAM roles for identity-based access — never access keys or hardcoded credentials
- Enable encryption at rest (`kms_key_id` or SSE) by default
- S3 buckets: `block_public_access` enabled, versioning enabled
- No hardcoded secrets, account IDs, or credentials in module code
