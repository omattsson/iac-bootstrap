---
name: create-terragrunt-stack
description: "Create or extend Terragrunt stacks, components, and environments. Use when: adding a new component to a stack, onboarding a new environment/site/region, creating _envcommon configs, wiring dependencies."
---

# Create Terragrunt Stack/Component

Creates or extends Terragrunt configurations following the workspace hierarchy.

## When to Use
- Adding a new component to an existing stack
- Onboarding a new stack in an existing environment
- Adding a new site/region
- Creating `_envcommon` shared configs for new modules

## Hierarchy

```
config/{environment}/{site}/{stack}/{component}/terragrunt.hcl
```

## Procedure

### Task A: Add a New Component

1. Create `_envcommon/{component}.hcl` with source URL, dependencies, inputs
2. Add module version to `subscription.hcl` → `module_tags`
3. Create `{component}/terragrunt.hcl` with includes

### Task B: Add a New Stack

1. Create `stack.hcl` with stack name, prefix
2. Copy component dirs from a sibling stack

## Validation Checklist
1. `terragrunt validate` passes
2. `terragrunt plan` shows expected resources
3. Module version tag exists in `subscription.hcl`
4. Dependencies have correct mock outputs
5. Shared config covers all required module variables
