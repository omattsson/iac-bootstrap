---
name: create-terraform-stack
description: "Create or extend Terraform environment stacks. Use when: adding a new module call to a stack, onboarding a new environment, creating backend configs, wiring module dependencies."
---

# Create Terraform Stack/Environment

Creates or extends Terraform root configurations in `environments/`.

## When to Use
- Adding a new module call to an existing stack
- Onboarding a new environment (dev, staging, prod)
- Adding a new stack in an existing environment
- Updating module version pins

## Stack Structure

```
environments/{environment}/{stack}/
├── main.tf       # Module calls + provider config
├── variables.tf  # Stack-level variables
├── outputs.tf    # Stack outputs
├── backend.tf    # S3 remote state backend
└── versions.tf   # Provider + module version pins
```

## Procedure

### Task A: Add a New Module Call

1. Add version to `versions.tf` → `module_versions`
2. Add module block in `main.tf` using `local.module_versions.{name}`
3. Expose required outputs in `outputs.tf`

### Task B: Add a New Stack

1. Create `environments/{environment}/{stack}/` directory
2. Create `backend.tf` with correct S3 key: `{environment}/{stack}/terraform.tfstate`
3. Create `versions.tf` with provider requirements and `module_versions` locals
4. Create `main.tf` with provider block and module calls
5. Create `variables.tf` and `outputs.tf`

### Task C: Add a New Environment

1. Copy an existing environment directory as a template
2. Update `backend.tf` key prefix to new environment name
3. Adjust variable defaults (region, account_id, tags) for the new environment

## Validation Checklist
1. `terraform init` succeeds
2. `terraform validate` passes
3. `terraform plan` shows expected resources
4. Module version tag exists in remote repo
5. S3 backend bucket and DynamoDB table exist in target account
