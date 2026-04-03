---
description: "Terragrunt configuration standards. Use when writing or modifying .hcl files including root configs, _envcommon templates, hierarchy files, and component configs."
applyTo: "core-infrastructure/**/*.hcl"
---

# Terragrunt Configuration Standards

## Hierarchy Files
- `subscription.hcl` — subscription_id, module_tags, identity config
- `site.hcl` — location, site_name
- `stack.hcl` — stack name, prefix
- `root.hcl` — remote state, provider generation, global input merge

## Shared Config Pattern (`_envcommon/`)
Every shared component config must:
1. Read hierarchy variables from parent files
2. Define source URL pointing to the module repo
3. Declare dependencies with realistic mock outputs
4. Provide inputs mapping hierarchy variables to module variables

## Component Config Pattern
```hcl
include "root" {
  path = find_in_parent_folders("root.hcl")
}

include "envcommon" {
  path = "${dirname(find_in_parent_folders("root.hcl"))}/_envcommon/{component}.hcl"
}
```

## Module Sources
`git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref=${local.module_tags.{name}}`
Version tags from `subscription.hcl`. Never hardcode versions in component files.
