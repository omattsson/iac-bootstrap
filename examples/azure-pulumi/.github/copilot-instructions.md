# Workspace Instructions — Contoso Infrastructure Automation

<!-- This is example generated output. The infra/ directory would exist in the
     target workspace, not in this bootstrap repo. -->

## Workspace Overview

This workspace contains infrastructure-as-code for Contoso's Azure platform, managed with **Pulumi (Python)**.

| Category | Repos/Dirs | Purpose |
|----------|------------|---------|
| **Pulumi Stacks** | `infra/` | Pulumi programs for all environments |
| **Shared Components** | `infra/components/` | Reusable `ComponentResource` classes |
| **Pipelines** | `iac-pipeline-templates/` | Azure DevOps pipeline templates |

## Stack Layout

```
infra/{stack-name}/
  Pulumi.yaml                   # Project metadata
  Pulumi.dev.yaml               # Dev stack config (non-secret values)
  Pulumi.prod.yaml              # Prod stack config
  __main__.py                   # Entry point
  requirements.txt
infra/components/               # Shared ComponentResource classes
  key_vault.py
  networking.py
```

## Naming Convention

`{prefix}-{abbreviation}-{suffix}` where prefix comes from stack config.
- Key Vault: `{prefix}-kv-{suffix}` (max 24 chars)
- Private Endpoints: `{prefix}-pe-{suffix}`
- Sanitize: `re.sub(r"[^0-9A-Za-z]+", "-", suffix).strip("-").lower()`

## Tagging Standard

```python
tags = {**default_tags, **resource_tags}
```
`resource_tags` wins on key conflicts.
Required tags: `environment`, `product`, `managed_by: Pulumi`.

## Stack Config Structure

Non-secret values in `Pulumi.{env}.yaml`:
```yaml
config:
  azure-native:location: westeurope
  contoso:environment: dev
  contoso:prefix: app-weu-dev
  contoso:resourceGroupName: rg-app-dev-weu
```

Secrets set via CLI:
```bash
pulumi config set --secret --stack dev contoso:clientSecret <value>
```

## Key Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **ComponentResources** — reusable resource groups encapsulated as classes in `infra/components/`
3. **No hardcoded secrets** — use `pulumi.Config("contoso").require_secret()` or Key Vault references
4. **Stack references** — cross-stack outputs via `pulumi.StackReference`, never hardcoded
5. **Preview before up** — always run `pulumi preview` before `pulumi up`
