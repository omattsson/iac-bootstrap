---
description: "Checkov custom policy conventions for Contoso Azure modules. Use when writing, modifying, or reviewing custom checkov checks in Python or YAML that enforce Contoso-specific security and compliance rules."
applyTo: "checks/**/*.py,checks/**/*.yaml,checks/**/*.yml"
---

# Checkov Custom Policy Standards

## When to Use Custom Checks
Write custom checks when built-in checkov rules don't cover:
- Contoso naming standards
- Required Contoso tag enforcement (`environment`, `product`, `managed_by`)
- Internal network hardening rules
- Azure-specific configurations required by Contoso security policy

## Check Layout

```
checks/
  contoso_naming.py          ← naming convention enforcement
  contoso_tags.py            ← required tag enforcement
  contoso_network.py         ← network hardening rules
  tests/
    test_contoso_naming.py
    test_contoso_tags.py
```

## Python Check Boilerplate

```python
from checkov.common.models.enums import CheckCategories, CheckResult
from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck


class CheckContosoRequiredTags(BaseResourceCheck):
    def __init__(self):
        name = "Ensure Azure resource has required Contoso tags"
        id = "CKV_CONTOSO_001"
        supported_resources = ["azurerm_key_vault", "azurerm_storage_account"]
        categories = [CheckCategories.GENERAL_SECURITY]
        super().__init__(name=name, id=id, categories=categories,
                         supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        tags = conf.get("tags", [{}])[0]
        for required_tag in ["environment", "product", "managed_by"]:
            if required_tag not in tags:
                return CheckResult.FAILED
        return CheckResult.PASSED


check = CheckContosoRequiredTags()
```

## Check ID Convention
`CKV_CONTOSO_NNN` — three-digit sequential number.
Never reuse or reassign IDs; retired checks keep their number.

| ID | Check |
|----|-------|
| `CKV_CONTOSO_001` | Required tags present |
| `CKV_CONTOSO_002` | Public network access disabled |
| `CKV_CONTOSO_003` | Private endpoint required |

## Severity Levels
| Severity | When to Use |
|----------|-------------|
| CRITICAL | Exposes data, public access on sensitive resources |
| HIGH | Disables security controls, missing encryption |
| MEDIUM | Missing best-practice config, non-standard naming |
| LOW | Minor compliance gaps |

## Running Checks
```bash
# Run all checks including Contoso custom checks
checkov -d . --external-checks-dir ./checks

# Run with compact output
checkov -d . --external-checks-dir ./checks --compact

# Run only Contoso custom checks
checkov -d . --external-checks-dir ./checks --check CKV_CONTOSO
```

## Pre-Commit Integration
```yaml
# .pre-commit-config.yaml
- repo: https://github.com/antonbabenko/pre-commit-terraform
  hooks:
    - id: terraform_checkov
      args:
        - --args=--external-checks-dir ./checks
```
