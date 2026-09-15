---
description: "Terragrunt configuration standards. Use when writing or modifying config files for Terragrunt including root configs, shared templates, hierarchy files, and component configs."
applyTo: "infrastructure-config/**/*.hcl"
---

# Terragrunt Configuration Standards

## Hierarchy Files
- `subscription.hcl` — subscription/account ID, module version pins
- `site.hcl` — region, location, site-specific values
- `stack.hcl` — stack name, prefix, stack-specific inputs
- `_envcommon/*.hcl` — shared module configs (source URL, dependencies, inputs)
- `{component}/terragrunt.hcl` — component-specific overrides only
<!-- Example for Terragrunt:
- `subscription.hcl` — subscription_id, module_tags, identity config
- `site.hcl` — location, site_name, maintenance windows
- `stack.hcl` — stack name, prefix, group prefixes
- `root.hcl` — remote state, provider generation, global input merge
-->

## Shared Config Pattern (_envcommon/*.hcl)
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
  path = "${dirname(find_in_parent_folders("subscription.hcl"))}/_envcommon/{module}.hcl"
  expose = true
  merge_strategy = "deep"
}

inputs = {
  # component-specific overrides only
}
```

## Module Sources
git::https://github.com/acme/tf-module-{name}?ref={tag}
Version tags from subscription.hcl → `locals.module_versions`. Never hardcode versions in component files.

## Dependencies
- Always declare dependencies explicitly with `dependency {}` blocks
- Always include `mock_outputs` for plan-time compatibility
- Set `mock_outputs_allowed_terraform_commands = ["validate", "plan"]`
- Use relative `config_path` references (e.g. `../networking`)
