# Contoso Infrastructure Automation

You are working in an infrastructure-as-code workspace for Contoso's Azure platform.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Terraform Modules** | `tf-module-*` | Reusable Azure resource modules |
| **Orchestration** | `core-infrastructure/` | Terragrunt config for all environments |
| **Pipelines** | `iac-pipeline-templates/` | Azure DevOps pipeline templates |

## Module Source Convention

```
git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref={tag}
```

Version tags managed in `subscription.hcl` → `module_tags` local.

## Standard Variable Set

These variables appear across all modules:
- `prefix` — Resource name prefix (e.g., `app-weu-dev`)
- `location` — Azure region (default: `westeurope`)
- `resource_group_name` — Target resource group
- `tags` — Additional tags (`map(string)`)
- `env_default_tags` — Default tags from Terragrunt inputs
- `subscription_id`, `tenant_id` — Azure identifiers

## Naming Convention

`{prefix}-{resource_abbreviation}-{suffix}`
- Key Vault: `{prefix}-kv-{suffix}` (max 24 chars, truncated with `substr`)
- Private Endpoints: `{prefix}-pe-{suffix}`
- All names sanitized: `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Optional `full_name` override on most modules

## Tagging Standard

```hcl
local.tags = merge(var.env_default_tags, var.tags)
```
Required tags: `environment`, `product`, `managed_by = "Terraform"`.

## Terragrunt Hierarchy

```
config/{environment}/{site}/{stack}/{component}/terragrunt.hcl
```
- `subscription.hcl` → Subscription ID, module versions
- `site.hcl` → Region, location
- `stack.hcl` → Stack name, prefix
- `_envcommon/*.hcl` → Shared module configs

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
local.name = substr(var.full_name != null ? var.full_name : "${var.prefix}-kv-${local.name_suffix}", 0, 24)
```

**Provider versions:**
```hcl
azurerm = { source = "hashicorp/azurerm", version = ">=4.21.0,<5.0" }
```

**No hardcoded secrets, account IDs, or credentials in module code.**

### Test Files (`**/*.tftest.hcl`)

**Required boilerplate:**
```hcl
mock_provider "azurerm" {}

override_data {
  target = data.azurerm_subscription.current
  values = { tenant_id = "00000000-0000-0000-0000-000000000000" }
}
```

- All tests: `command = plan` — never `command = apply`
- Include all `common.variables.tf` variables in `variables {}` block
- One test file per concern: `naming.tftest.hcl`, `tags.tftest.hcl`, etc.

### Terragrunt Files (`core-infrastructure/**/*.hcl`)

Hierarchy: subscription.hcl → site.hcl → stack.hcl → component/terragrunt.hcl

Shared config in `_envcommon/`:
- Read hierarchy variables from parent files
- Define source URL pointing to module repo
- Declare dependencies with realistic mock outputs
- Map hierarchy variables to module inputs

Version tags from `subscription.hcl`. Never hardcode versions in components.

### Pipelines

Two-stage: Plan → Apply (on protected branches with approval). Identity-based auth (MSI). Provider caching.

---

## Behavioral Rules

- DO NOT run `terraform apply` or `terraform destroy` without explicit approval
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT change `common.variables.tf` unless the variable is genuinely cross-module
- DO NOT break backward compatibility without explicit approval
- ONLY use `command = plan` in tests
- ALWAYS use `mock_provider "azurerm" {}` in tests
- ALWAYS provide `mock_outputs` in Terragrunt dependency blocks

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **DRY** — common config in `_envcommon`, variables flow from hierarchy
3. **No hardcoded secrets** — use Key Vault, MSI, or Terragrunt inputs
4. **Plan-only tests** — mock providers, no real resources
5. **Pre-commit hooks** — `terraform_fmt`, `tflint`, `checkov`, `terraform_docs`
