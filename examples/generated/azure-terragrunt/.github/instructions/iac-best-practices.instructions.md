---
description: "Universal IaC best practices for Terraform modules. Use when: reviewing infrastructure code, adding new resources, designing module interfaces, hardening security, or improving code quality. Covers naming, tagging, testing, security, state management."
applyTo: "**/*.tf"
---

# IaC Best Practices

## Module Design
- One module = one logical resource group. Don't combine unrelated resources.
- Consistent file layout: `main.tf`, `{resource}.tf`, `locals.tf`, `variables.tf`, `outputs.tf`, `versions.tf`
- Single-instance resources use identifier `"default"`. Multiple instances use `for_each`.
- Always provide a `full_name` override variable for naming flexibility.
- Truncate names to cloud provider max length with `substr()`.

## Variables
- Cross-module variables go in a shared file, module-specific in `variables.tf`
- Use `optional(type, default)` for object attributes (Terraform 1.3+)
- New variables must have defaults — never break existing consumers
- Feature toggles via `count` (bool) or conditional `for_each` (empty map)

## Naming & Tagging
- Sanitize inputs: `replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`
- Tag merge: `merge(var.env_default_tags, var.tags)` — resource-specific wins
- Required tags enforced at orchestration layer, not in modules

## Testing
- All tests: `command = plan`, `mock_provider`, no real resources
- One test file per concern (naming, tags, conditionals, outputs)
- Include ALL common variables in test `variables {}` block

## Security
- No hardcoded secrets, account IDs, or credentials
- `public_network_access_enabled = false` by default
- Private endpoint pattern: `for_each = var.private_endpoints` map
- Identity-based auth over service principals/access keys

## Backward Compatibility
- New variables must have defaults
- Deprecate, don't remove — prefix description with `DEPRECATED`
- Breaking changes = major version bump
