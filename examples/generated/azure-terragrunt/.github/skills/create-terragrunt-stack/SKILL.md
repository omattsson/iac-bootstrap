---
name: create-orchestration-stack
description: "Create or extend Terragrunt stacks, components, and environments. Use when: adding a new component to a stack, onboarding a new environment/region/stack, creating shared configs, wiring dependencies, debugging plan errors, managing version pins."
---

# Create Terragrunt Stack/Component

Creates or extends Terragrunt configurations following the workspace hierarchy pattern.

## When to Use
- Adding a new component to an existing stack
- Onboarding a new stack in an existing environment
- Adding a new region/site to an environment
- Creating shared configs for new modules
- Wiring cross-component dependencies
- Debugging plan errors related to orchestration config
- Managing module version pins across environments

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

## Procedure

### Task A: Add a New Component

#### 1. Create shared config
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
<!-- Populate with the workspace's actual shared config pattern -->

#### 2. Add module version
In subscription.hcl → `locals.module_versions`:
```hcl
module_versions = {
  tf-module-keyvault = "v1.2.0"
  tf-module-network   = "v2.0.1"
}
```

#### 3. Create component config
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

### Task B: Add a New Stack

#### 1. Create stack-level config
```hcl
locals {
  stack_name = "platform"
  prefix     = "${local.sub_vars.locals.env}-${local.stack_name}"
}
```

#### 2. Copy component dirs from a sibling stack

### Task C: Add a New Region/Site

#### 1. Create site-level config
```hcl
locals {
  location = "westeurope"
  region   = "weu"
}
```

## Dependency Patterns

### Mock outputs best practice
Always provide realistic mock outputs matching the dependency's actual output structure:
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

## Validation Checklist
1. `terragrunt validate` passes
2. `terragrunt plan` shows expected resources
3. Module version tag exists in version file
4. Dependencies have correct mock outputs
5. Shared config covers all required module variables
6. Stack-specific overrides are minimal (DRY)
