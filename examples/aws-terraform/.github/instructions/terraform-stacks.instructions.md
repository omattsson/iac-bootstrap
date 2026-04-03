---
description: "Terraform stack configuration standards. Use when writing or modifying .tf files in environments/ including root module configs, backend configs, and version pins."
applyTo: "environments/**/*.tf"
---

# Terraform Stack Standards

## Stack Files
- `main.tf` — provider block + module calls
- `variables.tf` — stack-level input variables
- `outputs.tf` — stack outputs (expose key module outputs)
- `backend.tf` — S3 remote state backend configuration
- `versions.tf` — required_providers + module version locals

## Backend Pattern
```hcl
terraform {
  backend "s3" {
    bucket         = "acme-terraform-state-{account_id}"
    key            = "{environment}/{stack}/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "acme-terraform-locks"
    encrypt        = true
  }
}
```

## Module Call Pattern
```hcl
locals {
  module_versions = {
    {name} = "v1.2.0"
  }
}

module "{name}" {
  source = "git::https://github.com/acme/tf-module-{name}.git?ref=${local.module_versions.{name}}"

  prefix           = var.prefix
  region           = var.region
  env_default_tags = var.env_default_tags
}
```

## Version Pinning
Version tags live in `versions.tf` → `module_versions` locals. Never hardcode `ref=` in `main.tf`.

## Dependencies
Use module output references directly — no separate dependency declarations needed for plain Terraform.
