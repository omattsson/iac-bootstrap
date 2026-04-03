---
description: "Terraform coding standards for Acme AWS modules. Use when writing or modifying .tf files including resources, variables, outputs, locals, and provider configurations."
applyTo: "tf-module-*/**/*.tf"
---

# Terraform Module Standards

## File Organization
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by AWS resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs
- `versions.tf` — terraform and provider version constraints

## Resource Conventions
- All single resources use identifier `"default"` (e.g., `aws_s3_bucket.default`)
- Map-driven resources use `for_each` with descriptive keys
- Use `count` for boolean on/off features
- Tags: `local.tags = merge(var.env_default_tags, var.tags)` — always

## Naming Pattern
```hcl
local.name = var.full_name != null ? var.full_name : "${var.prefix}-{abbr}-${local.name_suffix}"
```
All names use `lower(regexreplace(...))` for sanitization — AWS resource names are case-sensitive and often lowercase-only.

## Variable Conventions
- Use `optional(type, default)` syntax (Terraform 1.3+) for object attributes
- Complex descriptions use `<<-EOT` heredoc format
- All variables need `type`, `description`, and sensible `default` where possible

## Provider Versions
```hcl
aws = { source = "hashicorp/aws", version = ">=5.0,<6.0" }
```

## No hardcoded secrets, account IDs, or credentials in module code.
