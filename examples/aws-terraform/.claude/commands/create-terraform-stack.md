# Create Terraform Stack/Environment

Create or extend Terraform root configurations in `environments/`.

## Usage
Describe what to add as the argument: `$ARGUMENTS`

If unclear, ask:
- Adding a module call, a new stack, or a new environment?
- Which module does it use?
- Target AWS account and region?

## Stack Structure

```
environments/{environment}/{stack}/
├── main.tf       # Module calls + provider config
├── variables.tf  # Stack-level variables
├── outputs.tf    # Stack outputs
├── backend.tf    # S3 remote state backend
└── versions.tf   # Provider + module version pins
```

## Task A: Add a New Module Call

### 1. Add version to `versions.tf` → `module_versions`
```hcl
locals {
  module_versions = {
    {name} = "v1.0.0"
  }
}
```

### 2. Add module block in `main.tf`
```hcl
module "{name}" {
  source = "git::https://github.com/acme/tf-module-{name}.git?ref=${local.module_versions.{name}}"

  prefix           = var.prefix
  region           = var.region
  env_default_tags = var.env_default_tags
}
```

### 3. Expose outputs in `outputs.tf`
```hcl
output "{name}_arn" {
  value = module.{name}.arn
}
```

## Task B: Add a New Stack

### 1. Create `environments/{environment}/{stack}/backend.tf`
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

### 2. Create `versions.tf`, `main.tf`, `variables.tf`, `outputs.tf`

## Task C: Add a New Environment

1. Copy an existing environment directory
2. Update `backend.tf` S3 key prefix to new environment name
3. Adjust variable defaults for the target account and region

## Validation
```bash
terraform init
terraform validate
terraform plan
```
