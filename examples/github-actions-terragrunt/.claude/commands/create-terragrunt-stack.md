# Create Terragrunt Stack/Component

Create or extend Terragrunt configurations following the workspace hierarchy.

## Usage
Describe what to add as the argument: `$ARGUMENTS`

If unclear, ask:
- Adding a component, a stack, or a new region/site?
- Which module does it use?
- What are its dependencies?

## Hierarchy

```
infrastructure-config/{environment}/{site}/{stack}/{component}/terragrunt.hcl
```

- `account.hcl` — AWS account ID, module versions
- `site.hcl` — region, site name
- `stack.hcl` — stack name, prefix
- `_envcommon/*.hcl` — shared module configs

## Task A: Add a New Component

### 1. Create shared config in `_envcommon/{component}.hcl`
```hcl
locals {
  account_vars = read_terragrunt_config(find_in_parent_folders("account.hcl"))
  site_vars    = read_terragrunt_config(find_in_parent_folders("site.hcl"))
  stack_vars   = read_terragrunt_config(find_in_parent_folders("stack.hcl"))
  module_tags  = local.account_vars.locals.module_tags
}

terraform {
  source = "git::https://github.com/acme-infra/tf-module-{name}?ref=${local.module_tags.{name}}"
}

dependency "vpc" {
  config_path = "../vpc"
  mock_outputs = {
    vpc_id = "mock-vpc-id"
  }
}

inputs = {
  prefix = local.stack_vars.locals.prefix
  region = local.site_vars.locals.region
  vpc_id = dependency.vpc.outputs.vpc_id
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
