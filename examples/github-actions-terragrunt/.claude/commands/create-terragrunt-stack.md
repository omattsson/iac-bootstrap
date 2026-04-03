# Create Terragrunt Stack/Component

Create or extend Terragrunt configurations following the workspace hierarchy.

## Usage
Describe what to add as the argument: `$ARGUMENTS`

If unclear, ask:
- Adding a component, a stack, or a new region?
- Which module does it use?
- What are its dependencies?

## Hierarchy

```
config/{environment}/{region}/{stack}/{component}/terragrunt.hcl
```

- `account.hcl` — account ID, module versions
- `region.hcl` — AWS region, availability zones
- `stack.hcl` — stack name, prefix
- `_envcommon/*.hcl` — shared module configs

## Task A: Add a New Component

### 1. Create shared config in `_envcommon/{component}.hcl`
```hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))
  stack_vars   = read_terragrunt_config(find_in_parent_folders("stack.hcl"))
  module_tags  = local.account_vars.locals.module_tags
}

terraform {
  source = "git::https://github.com/acme-infra/tf-module-{name}?ref=${local.module_tags.{name}}"
}

dependency "vpc" {
  config_path = "../vpc"
  mock_outputs = {
    id = "mock-vpc-id"
  }
}

inputs = {
  prefix     = local.stack_vars.locals.prefix
  region     = local.region_vars.locals.aws_region
  vpc_id     = dependency.vpc.outputs.id
}
```

### 2. Add version in `account.hcl` → `module_tags`

### 3. Create `{component}/terragrunt.hcl`
```hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/{component}.hcl"
}
```

## Validation
```bash
terragrunt validate
terragrunt plan
```
