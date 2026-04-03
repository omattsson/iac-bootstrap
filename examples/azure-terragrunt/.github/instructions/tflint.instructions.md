---
description: "tflint custom rule conventions for Contoso Azure modules. Use when writing, modifying, or reviewing custom tflint rules or .tflint.hcl configurations that enforce Contoso Terraform coding standards."
applyTo: "{rules/**/*.go,**/.tflint.hcl}"
---

# tflint Custom Rule Standards

## Workspace tflint Configuration

```hcl
# .tflint.hcl (repo root)
plugin "azurerm" {
  enabled = true
  version = "0.27.0"
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

plugin "contoso" {
  enabled = true
  version = "1.0.0"
  source  = "github.com/contoso/tflint-ruleset-contoso"
}

rule "contoso_naming_convention" {
  enabled = true
}

rule "contoso_required_tags_variable" {
  enabled = true
}
```

## When to Write Custom Rules
Write custom tflint rules when:
- Enforcing `{prefix}-{abbreviation}-{suffix}` naming pattern across all modules
- Banning deprecated Azure resource types
- Requiring specific variable declarations (e.g., `common.variables.tf` inclusion)
- Enforcing argument-level requirements not covered by azurerm plugin

For value-based compliance checks, prefer checkov. Use tflint for structural/AST checks.

## Rule Plugin Layout

```
tflint-ruleset-contoso/
  rules/
    contoso_naming_convention.go
    contoso_naming_convention_test.go
    contoso_required_tags_variable.go
    contoso_required_tags_variable_test.go
  main.go
  go.mod
  go.sum
```

## Rule Boilerplate

```go
package rules

import (
    "github.com/terraform-linters/tflint-plugin-sdk/hclext"
    "github.com/terraform-linters/tflint-plugin-sdk/tflint"
)

type ContosoNamingConventionRule struct {
    tflint.DefaultRule
}

func NewContosoNamingConventionRule() *ContosoNamingConventionRule {
    return &ContosoNamingConventionRule{}
}

func (r *ContosoNamingConventionRule) Name() string {
    return "contoso_naming_convention"
}

func (r *ContosoNamingConventionRule) Enabled() bool { return true }

func (r *ContosoNamingConventionRule) Severity() tflint.Severity {
    return tflint.ERROR
}

func (r *ContosoNamingConventionRule) Link() string {
    return "https://contoso.github.io/tflint-rules/contoso_naming_convention"
}

func (r *ContosoNamingConventionRule) Check(runner tflint.Runner) error {
    // Implementation: verify resource name follows {prefix}-{abbreviation}-{suffix}
    return nil
}
```

## Severity Guidelines
| Level | When to Use |
|-------|-------------|
| `ERROR` | Naming violations, banned resources — blocks CI |
| `WARNING` | Non-standard patterns, missing recommended args |
| `NOTICE` | Informational / stylistic suggestions |

## Running tflint
```bash
# Install plugins and run recursively
tflint --init
tflint --recursive

# Run on a specific module
tflint --chdir=./tf-module-key-vault
```

## Pre-Commit Integration
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/antonbabenko/pre-commit-terraform
  hooks:
    - id: terraform_tflint
      args:
        - --args=--config __GIT_WORKING_DIR__/.tflint.hcl
```
