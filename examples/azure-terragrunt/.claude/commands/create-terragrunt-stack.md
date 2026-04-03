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
config/{environment}/{site}/{stack}/{component}/terragrunt.hcl
```

- `subscription.hcl` — subscription ID, module versions
- `site.hcl` — location, site name
- `stack.hcl` — stack name, prefix
- `_envcommon/*.hcl` — shared module configs

## Task A: Add a New Component

### 1. Create shared config in `_envcommon/{component}.hcl`
```hcl
locals {
  subscription_vars = read_terragrunt_config(find_in_parent_folders("subscription.hcl"))
  site_vars         = read_terragrunt_config(find_in_parent_folders("site.hcl"))
  stack_vars        = read_terragrunt_config(find_in_parent_folders("stack.hcl"))
  module_tags       = local.subscription_vars.locals.module_tags
}

terraform {
  source = "git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref=${local.module_tags.{name}}"
}

dependency "resource_group" {
  config_path = "../resource-group"
  mock_outputs = {
    name = "mock-rg"
  }
}

inputs = {
  prefix              = local.stack_vars.locals.prefix
  location            = local.site_vars.locals.location
  resource_group_name = dependency.resource_group.outputs.name
}
```

### 2. Add version in `subscription.hcl` → `module_tags`

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
