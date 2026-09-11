# Acme Corp Infrastructure Automation

You are working in an infrastructure-as-code workspace for Acme Corp's Azure platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable Azure resource modules |
| **Orchestration** | `infrastructure-config/` | Terragrunt config for all environments |
| **Pipelines** | `.github/workflows/` | GitHub Actions pipeline templates |

## Module Source Convention

git::https://github.com/acme/tf-module-{name}?ref={tag}

Version tags managed in subscription.hcl → `locals.module_versions`.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix
- `location` — Azure region (e.g. westeurope)
- `resource_group_name` — Target resource group
- `tags` — Resource-specific tags (map(string))
- `env_default_tags` — Environment-wide default tags from orchestration

## Naming Convention

{prefix}-{resource_abbreviation}-{suffix}

## Tagging Standard

merge(var.env_default_tags, var.tags)

## Environment Hierarchy

config/{environment}/{region}/{stack}/{component}/terragrunt.hcl

Hierarchy files:
- subscription.hcl — account/subscription ID, module versions
- site.hcl — region, location
- stack.hcl — stack name, prefix
- _envcommon/*.hcl — shared module configs

---

## Coding Standards

### Terraform Files (`tf-module-*/**/*.tf`)

**File organization:**
- `main.tf` — provider requirements + data sources
- `{resource}.tf` — core resources, named by Azure resource type
- `locals.tf` — name construction, tag merging, computed values
- `variables.tf` — module-specific variables
- `common.variables.tf` — standard cross-module variables
- `outputs.tf` — module outputs (at minimum: `name` and `id`)
- `versions.tf` — terraform and provider version constraints

**Resource conventions:**
- Single resources use identifier `"default"` (e.g., `azurerm_key_vault.default`)
- Map-driven resources use `for_each` with descriptive keys
- Boolean toggles use `count`
- Tags: `merge(var.env_default_tags, var.tags)` — always

**Naming pattern:**
```hcl
name = "${var.prefix}-${local.resource_abbreviation}-${local.suffix}"
```

**Variable conventions:**
- Use `optional(type, default)` syntax (Terraform 1.3+) for object attributes
- Complex descriptions use `<<-EOT` heredoc format
- All variables need `type`, `description`, and sensible `default` where possible

**Provider versions:**
```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">=4.0.0,<5.0.0"
    }
  }
}
```

**No hardcoded secrets, account IDs, or credentials in module code.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate in every test:**
```hcl
mock_provider "azurerm" {}

override_data {
  target = data.azurerm_subscription.current
  values = {
    subscription_id = "00000000-0000-0000-0000-000000000000"
    tenant_id       = "00000000-0000-0000-0000-000000000000"
  }
}
```

- All tests use `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in the `variables {}` block
- One test file per concern: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.
- Run names: `snake_case` descriptive names

### Orchestration Files (`infrastructure-config/**/*.hcl`)

- `subscription.hcl` — subscription/account ID, module version pins
- `site.hcl` — region, location, site-specific values
- `stack.hcl` — stack name, prefix, stack-specific inputs
- `_envcommon/*.hcl` — shared module configs (source URL, dependencies, inputs)
- `{component}/terragrunt.hcl` — component-specific overrides only

**Shared config pattern (_envcommon/*.hcl):**
- Read hierarchy variables from parent files
- Define source URL pointing to the module repo
- Declare dependencies with realistic mock outputs
- Provide inputs mapping hierarchy variables to module variables

**Component config pattern:**
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

Version tags from subscription.hcl → `locals.module_versions`. Never hardcode versions in component files.

### Pipeline Files

**Two-stage pattern:** Plan stage → Apply stage (on protected branches with approval).

Use OIDC federation — no long-lived secrets in workflow files.
Configure `permissions: id-token: write` and use the provider's official login action.

Use reusable workflows (`workflow_call`) for plan/apply stages.
Reference shared templates via `uses: {org}/{repo}/.github/workflows/{template}.yml@{ref}`.

---

## Module Maintenance & Backward Compatibility

### Adding optional variables (non-breaking)
Always provide a default that preserves existing behavior. Use `optional()` for new object attributes:

```hcl
# New simple variable — default keeps existing behavior
variable "enable_purge_protection" {
  type    = bool
  default = false
}

# New attribute on existing object — optional() so callers don't have to update
variable "network_config" {
  type = object({
    public_access         = optional(bool, false)
    allowed_cidrs         = optional(list(string), [])
    bypass_azure_services = optional(bool, false)  # new — callers unaffected
  })
  default = {}
}
```

### Deprecating variables
Keep the old variable, add a `DEPRECATED` description, and resolve both in `locals`:

```hcl
variable "old_var_name" {
  type        = string
  default     = null
  description = "DEPRECATED: use `new_var_name` instead. Removed in next major version."
}

variable "new_var_name" {
  type    = string
  default = "default-value"
}

locals {
  resolved_value = var.old_var_name != null ? var.old_var_name : var.new_var_name
}
```

### Renaming resources with `moved` blocks
Add a `moved` block in the same commit as any resource or `for_each` key rename. Prevents destroy/re-create:

```hcl
moved {
  from = azurerm_key_vault.old_name
  to   = azurerm_key_vault.default
}
```

### Semantic versioning

| Change | Version bump |
|--------|-------------|
| Bug fix, doc update | Patch (`x.y.Z`) |
| New optional variable, new output | Minor (`x.Y.0`) |
| Removed/renamed variable, changed output type | Major (`X.0.0`) |

### Major version migration guides
For every major version bump, publish a `MIGRATION.md` at the root of the module repository (not the consuming workspace) and release it alongside the corresponding major-version tag. Document: what broke, old vs new usage, and step-by-step upgrade instructions.

---

## Behavioral Rules

### When building or modifying Terraform modules:
- DO NOT run `terraform apply` or `terraform destroy`
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests

### When writing tests:
- DO NOT use `command = apply`
- DO NOT create real cloud resources
- ALWAYS include all required `common.variables.tf` variables
- ALWAYS use `mock_provider "azurerm" {}`

### When modifying orchestration configs:
- DO NOT run apply or destroy without explicit approval
- DO NOT hardcode account IDs or credentials
- DO NOT modify root configs without understanding impact on all stacks
- DO NOT bypass the DRY pattern
- ALWAYS provide mock_outputs in dependency blocks

### General principles:
1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config extracted, variables flow from hierarchy
3. **No hardcoded secrets** — use secret manager, identity-based auth
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, validation
