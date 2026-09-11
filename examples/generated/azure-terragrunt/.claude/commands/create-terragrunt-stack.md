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
config/
├── subscription.hcl          # account/subscription ID, module versions
└── {environment}/
    ├── site.hcl              # region, location
    └── {stack}/
        ├── stack.hcl         # stack name, prefix
        ├── _envcommon/       # shared module configs
        │   └── {module}.hcl
        └── {component}/
            └── terragrunt.hcl
```

## Task A: Add a New Component

### 1. Create shared config
```hcl
locals {
  sub_vars  = read_terragrunt_config(find_in_parent_folders("subscription.hcl"))
  site_vars = read_terragrunt_config(find_in_parent_folders("site.hcl"))
  stack_vars = read_terragrunt_config(find_in_parent_folders("stack.hcl"))
}

terraform {
  source = "git::https://github.com/{org}/{module}?ref=${local.sub_vars.locals.module_versions.{module}}"
}

dependency "{dep}" {
  config_path = "../{dep}"
  mock_outputs = {
    id   = "mock-id"
    name = "mock-name"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  prefix   = local.stack_vars.locals.prefix
  location = local.site_vars.locals.location
}
```

### 2. Add module version
In subscription.hcl → `locals.module_versions`:
```hcl
module_versions = {
  tf-module-keyvault = "v1.2.0"
  tf-module-network   = "v2.0.1"
}
```

### 3. Create component config
```hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path = "${dirname(find_in_parent_folders("subscription.hcl"))}/_envcommon/{module}.hcl"
  expose = true
  merge_strategy = "deep"
}

inputs = {
  # component-specific overrides only
}
```

## Task B: Add a New Stack

### 1. Create stack-level config
```hcl
locals {
  stack_name = "platform"
  prefix     = "${local.sub_vars.locals.env}-${local.stack_name}"
}
```

### 2. Copy component dirs from a sibling stack

## Task C: Add a New Region/Site

### 1. Create site-level config
```hcl
locals {
  location = "westeurope"
  region   = "weu"
}
```

## Dependency Pattern

Always provide realistic mock outputs:
```hcl
dependency "networking" {
  config_path = "../networking"
  mock_outputs = {
    vnet_id            = "mock-vnet-id"
    subnet_ids         = { default = "mock-subnet-id" }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}
```

## Validation

After creating:
```bash
terragrunt validate
terragrunt plan
```

Check: module version exists, dependencies have mock outputs, shared config covers all variables, overrides are minimal (DRY).
