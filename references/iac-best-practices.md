# IaC Best Practices — Universal Patterns

Battle-tested infrastructure-as-code patterns extracted from production Azure environments. These are cloud-agnostic principles — adapt the specific syntax to your provider and tooling.

## 1. Module Design

### Single-Responsibility Modules
Each module manages one logical resource group (e.g., Key Vault + its access policies + its private endpoints). Don't combine unrelated resources.

```
Good:  tf-module-key-vault (vault + policies + PE + diagnostics)
Bad:   tf-module-security (vault + NSG + WAF + certificates)
```

### Consistent File Layout
Every module should follow the same file structure. New team members should know exactly where to find things:

| File | Purpose | Rule |
|------|---------|------|
| `main.tf` | Provider requirements + data sources | Only provider config and data lookups |
| `{resource}.tf` | Core resource(s) | Named after the primary Azure/AWS/GCP resource |
| `locals.tf` | Name construction, tag merging, computed values | All naming logic centralized here |
| `variables.tf` | Module-specific inputs | Only variables unique to this module |
| `common.variables.tf` | Cross-module standard variables | Identical across all modules — copy, don't diverge |
| `outputs.tf` | Module outputs | At minimum: `name` and `id` |
| `versions.tf` | Terraform + provider constraints | Pin major, float minor: `>=4.0,<5.0` |

### Resource Identifier Convention
Use a consistent identifier for single-instance resources:
```hcl
# Good: predictable, grepable
resource "azurerm_key_vault" "default" { ... }
resource "aws_s3_bucket" "default" { ... }

# For multiple instances: for_each with descriptive keys
resource "azurerm_private_endpoint" "default" {
  for_each = var.private_endpoints
  name     = "${local.name}-pe-${each.key}"
}
```

### Full-Name Override Pattern
Always allow consumers to bypass your naming logic:
```hcl
variable "full_name" {
  type        = string
  default     = null
  description = "Override the auto-generated name"
}

locals {
  name = var.full_name != null ? var.full_name : "${var.prefix}-${var.abbreviation}-${local.suffix}"
}
```

### Resource Name Length Safety
Cloud providers have different name limits (Key Vault: 24, Storage Account: 24, etc.). Always truncate:
```hcl
locals {
  name = substr(local.unsafe_name, 0, 24)  # Enforce max length
}
```

---

## 2. Naming & Tagging

### Name Sanitization
User inputs contain special characters. Always sanitize:
```hcl
locals {
  name_suffix = lower(trimprefix(trimsuffix(
    replace(var.suffix, "/[^0-9A-Za-z]+/", "-"), "-"), "-"))
}
```

### Tag Merge Strategy
Define a clear merge order where resource-specific tags win:
```hcl
locals {
  tags = merge(var.env_default_tags, var.tags)
}
```

**Rules:**
- Default tags come from the orchestration layer (environment, product, managed_by)
- Resource-specific tags override defaults on key conflict
- Required tags enforced at the orchestration layer, not in modules
- Modules never hardcode tags — they only merge

### Required Tags
Enforce these at the orchestration/pipeline layer:
- `managed_by = "Terraform"` — distinguishes IaC-managed resources
- `environment` — dev, staging, prod
- `product` / `service` — cost allocation
- `tf_project_path` — trace back to the source code that created it

---

## 3. Variable Design

### Common Variables File
Maintain a `common.variables.tf` that's identical across all modules. This is the contract between your orchestration layer and your modules:
```hcl
variable "prefix"              { type = string }
variable "location"            { type = string, default = "westeurope" }
variable "resource_group_name" { type = string }
variable "tags"                { type = map(string), default = {} }
variable "env_default_tags"    { type = map(string), default = {} }
```

**Why:** When every module accepts the same base variables, your orchestration layer can pass them uniformly without per-module special-casing.

### Optional with Defaults
Use Terraform 1.3+ `optional()` for complex objects so consumers only specify what they care about:
```hcl
variable "network_config" {
  type = object({
    public_access  = optional(bool, false)
    allowed_cidrs  = optional(list(string), [])
    private_endpoints = optional(map(object({
      subnet_id        = string
      subresource_name = string
    })), {})
  })
  default = {}
}
```

### Feature Toggles
Use boolean variables with `count` or conditional `for_each` for optional features:
```hcl
variable "enable_rbac" {
  type    = bool
  default = false
}

# Created only when RBAC enabled
resource "azurerm_role_assignment" "admin" {
  count = var.enable_rbac ? 1 : 0
  ...
}

# Created only when RBAC disabled (legacy access policies)
resource "azurerm_key_vault_access_policy" "default" {
  for_each = var.enable_rbac ? {} : var.access_policies
  ...
}
```

---

## 4. Testing

### Plan-Only Tests
Never create real resources in tests. Use `command = plan` with mock providers:
```hcl
mock_provider "azurerm" {}

run "creates_resource_with_correct_name" {
  command = plan
  assert {
    condition     = azurerm_key_vault.default.name == "expected-name"
    error_message = "Name doesn't match convention"
  }
}
```

**Why:** Tests run in seconds, cost nothing, need no cloud credentials, and can run in any CI environment.

### Test Organization
One file per concern — not one monolithic test file:
- `naming.tftest.hcl` — name construction, truncation, overrides
- `tags.tftest.hcl` — tag merging, conflict resolution, empty maps
- `conditional.tftest.hcl` — feature toggles, count/for_each behavior
- `outputs.tftest.hcl` — output values populated correctly
- `private_endpoints.tftest.hcl` — PE creation, naming, empty map

### Data Source Overrides
Mock data sources that call cloud APIs:
```hcl
override_data {
  target = data.azurerm_subscription.current
  values = { tenant_id = "00000000-0000-0000-0000-000000000000" }
}
```

### Test Variables
Always include ALL required variables. Missing variables cause confusing errors:
```hcl
variables {
  prefix              = "test-auto"
  location            = "swedencentral"
  resource_group_name = "test-rg"
  tags                = {}
  env_default_tags    = { managed_by = "Terraform" }
  # Don't forget common.variables.tf vars!
}
```

---

## 5. Orchestration (Terragrunt / Terramate / Workspaces)

### DRY Hierarchy
Never repeat configuration. Extract shared config into a common layer:
```
_envcommon/keyvault.hcl    ← shared inputs, dependencies, source URL
config/dev/keyvault/       ← includes shared + only overrides what differs
config/prod/keyvault/      ← includes shared + only overrides what differs
```

### Dependency Management
- Always declare dependencies explicitly
- Provide realistic `mock_outputs` for plan-time validation
- Mock outputs must match the actual module's output structure

```hcl
dependency "vnet" {
  config_path = "../vnet"
  mock_outputs = {
    vnet_id = "/subscriptions/.../providers/Microsoft.Network/virtualNetworks/mock"
    subnets = { "default" = "/subscriptions/.../subnets/default" }
  }
}
```

### Version Pinning
- Pin module versions per environment (dev can be ahead of prod)
- Never update all environments simultaneously
- Roll out: dev → staging → prod with plan verification at each step
- Store version tags in a dedicated file, not scattered in component configs

### Input Flow
Establish a clear hierarchy where variables merge predictably:
```
account/subscription-level → region/site-level → stack-level → component-level
```
Each level can override the previous. Document the merge order.

---

## 6. CI/CD Pipelines

### Plan → Approve → Apply
Every pipeline must follow this flow:
1. **Plan** — runs on every push/PR, publishes plan as artifact
2. **Review** — human or automated approval gate (skip for dev if appropriate)
3. **Apply** — only on protected branches, uses the saved plan artifact

**Never apply without a saved plan.** Re-planning during apply can cause drift.

### Drift Detection
Schedule periodic plan-only runs on main branch:
- Run daily or weekly depending on environment criticality
- Notify the team (Slack/Teams/email) when drift is detected
- Don't auto-remediate — drift often indicates manual changes that need investigation

### Authentication
- **Prefer identity-based auth** (Managed Identity, OIDC, Workload Identity) over secrets
- Never store credentials in pipeline YAML
- Use separate identities per environment (dev MSI ≠ prod MSI)

### Provider Caching
Cache Terraform providers across pipeline runs to speed up `init`:
```
--provider-cache --provider-cache-dir /tmp/providers/
```

### Lock Timeout
In shared environments, set a generous lock timeout:
```
-lock-timeout=20m
```

---

## 7. Security

### No Hardcoded Secrets
- No passwords, API keys, tokens, or connection strings in `.tf` or `.hcl` files
- Use Key Vault / Secrets Manager / Parameter Store references
- Use identity-based auth wherever possible

### Network Hardening by Default
```hcl
variable "public_network_access_enabled" {
  type    = bool
  default = false  # Secure by default
}
```
Require explicit opt-in for public access. Combine with private endpoints.

### Private Endpoint Pattern
Every module that supports private connectivity should follow a consistent pattern:
```hcl
variable "private_endpoints" {
  type = map(object({
    subnet_id        = string
    subresource_name = string
    dns_zone_id      = optional(string)
  }))
  default     = {}
  description = "Map of private endpoints to create"
}

resource "..._private_endpoint" "default" {
  for_each = var.private_endpoints
  # consistent naming: {resource_name}-pe-{key}
}
```

### Least Privilege
- Terraform identity gets only what it needs per environment
- Use separate identities for plan vs apply when possible
- Audit role assignments periodically

---

## 8. Code Quality

### Pre-Commit Hooks
Automate quality checks before code leaves the developer's machine:
```yaml
repos:
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    hooks:
      - id: terraform_fmt          # Consistent formatting
      - id: terraform_tflint       # Linting
      - id: terraform_checkov      # Security scanning
      - id: terraform_docs         # Auto-generate README
```

### Formatting
Run `terraform fmt -recursive` before every commit. Non-negotiable.

### Documentation
- Every module has a README with auto-generated variable/output tables
- Use `.terraform-docs.yml` for consistent doc generation
- Examples in `examples/` directory — at least one basic example

### Backward Compatibility
- New variables must have defaults (existing consumers shouldn't break)
- Use `optional()` for new object attributes
- Deprecate, don't remove — add `DEPRECATED` prefix to description
- Breaking changes require a major version bump

---

## 9. State Management

### Remote State Only
Never use local state in shared environments. Configure remote backend:
- Azure: Storage Account with AAD auth and versioning
- AWS: S3 + DynamoDB for locking
- GCP: GCS with state locking

### State File Per Component
One state file per deployable unit. Don't put your entire infrastructure in one state:
```
Good: keyvault/ → keyvault/terraform.tfstate
      aks/      → aks/terraform.tfstate

Bad:  all-infra/ → terraform.tfstate (blast radius = everything)
```

### State Encryption
Enable encryption at rest for state storage. State contains sensitive values.

---

## 10. Progressive Rollout

### Environment Promotion
```
dev → staging → prod
```
- Each environment pins its own module versions
- Promote by updating the version pin, not by copying code
- Always plan in the target environment before applying

### Blast Radius Reduction
- Small modules → small state files → small blast radius
- Separate stateful resources (databases) from stateless (compute)
- Use `prevent_destroy` lifecycle on critical resources:
```hcl
lifecycle {
  prevent_destroy = true
}
```
