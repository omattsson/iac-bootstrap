# Contoso Infrastructure Automation — Pulumi

You are working in an infrastructure-as-code workspace for Contoso's Azure platform, managed with **Pulumi (Python)**.

## Workspace Structure

| Category | Path | Purpose |
|----------|------|---------|
| **Pulumi Stacks** | `infra/` | Pulumi programs for all environments |
| **Shared Components** | `infra/components/` | Reusable `ComponentResource` classes |
| **Pipelines** | `iac-pipeline-templates/` | Azure DevOps pipeline templates |

## Stack Layout

```
infra/
  components/                   ← shared ComponentResource classes
    key_vault.py
    networking.py
  networking/                   ← networking stack (deployed first)
    Pulumi.yaml
    Pulumi.dev.yaml
    Pulumi.prod.yaml
    __main__.py
    requirements.txt
  security/                     ← depends on networking
    ...
  app/                          ← depends on networking + security
    ...
```

## Naming Convention

`f"{prefix}-{abbreviation}-{suffix}"` with max-length enforcement.
Sanitize: `re.sub(r"[^0-9A-Za-z]+", "-", suffix).strip("-").lower()`
- Key Vault: `(f"{prefix}-kv-{suffix}")[:24]` (max 24 chars)

## Tagging Standard

```python
tags = {**default_tags, **resource_tags}
```
`resource_tags` wins on key conflicts.
Required tags: `environment`, `managed_by: Pulumi`, `product`.

## Stack Config Structure

Non-secret values in `Pulumi.{env}.yaml`:
```yaml
config:
  azure-native:location: westeurope
  contoso:environment: dev
  contoso:prefix: app-weu-dev
  contoso:resourceGroupName: rg-app-dev-weu
  contoso:tenantId: "00000000-0000-0000-0000-000000000000"
```

Secrets set via CLI (stored encrypted in `Pulumi.{env}.yaml`):
```bash
pulumi config set --secret --stack dev contoso:clientSecret <value>
```

## State Backend

`PULUMI_BACKEND_URL=azblob://tfstate?storage_account=contosotfstateweu`

---

## Coding Standards

### Entry Points (`infra/{stack}/__main__.py`)

- Read all config at the top via `pulumi.Config()`
- Instantiate `ComponentResource` classes from `infra/components/`
- Export outputs at the bottom: `pulumi.export("vault_id", kv.vault.id)`
- No resource definitions directly in `__main__.py` — use ComponentResources

### ComponentResources (`infra/components/*.py`)

```python
import pulumi
import pulumi_azure_native as azure

class KeyVaultComponent(pulumi.ComponentResource):
    def __init__(self, name: str, args: dict, opts: pulumi.ResourceOptions | None = None):
        super().__init__("contoso:components:KeyVault", name, {}, opts)
        child_opts = pulumi.ResourceOptions(parent=self)

        self.vault = azure.keyvault.Vault(
            f"{name}-vault",
            azure.keyvault.VaultArgs(
                resource_group_name=args["resource_group_name"],
                location=args["location"],
                properties=azure.keyvault.VaultPropertiesArgs(
                    sku=azure.keyvault.SkuArgs(family="A", name="standard"),
                    tenant_id=args["tenant_id"],
                    enable_rbac_authorization=True,
                ),
                tags={**args.get("default_tags", {}), **args.get("tags", {})},
            ),
            opts=child_opts,
        )

        self.register_outputs({"vault_id": self.vault.id})
```

### Cross-Stack References

```python
networking = pulumi.StackReference(f"contoso/networking/{env}")
vnet_id = networking.get_output("vnet_id")
# Always handle None for plan-time safety
```

### Secrets

- Read with: `pulumi.Config().require_secret("clientSecret")`
- Never log or `pulumi.export` secret values
- Rotate via: `pulumi config set --secret --stack {env} contoso:clientSecret <new-value>`

### Pipelines

Two-stage: Preview → Apply (on protected branches with approval). MSI/OIDC auth. No secrets in pipeline YAML.

---

## Behavioral Rules

- DO NOT run `pulumi up` or `pulumi destroy` without explicit approval
- DO NOT hardcode secrets, account IDs, or credentials
- DO NOT store secrets as plaintext in `Pulumi.{env}.yaml`
- DO NOT define resources directly in `__main__.py` — use `ComponentResource`
- ALWAYS call `self.register_outputs({...})` in every `ComponentResource`
- ALWAYS handle `None` when reading `StackReference` outputs
- ALWAYS run `pulumi preview` before `pulumi up`

## Principles

1. **Minimal intervention** — smallest change that fulfills the requirement
2. **ComponentResources** — all reusable resource groups encapsulated as classes
3. **No hardcoded secrets** — `pulumi.Config().require_secret()` or Key Vault references
4. **Stack references** — cross-stack values via `pulumi.StackReference`, never hardcoded
5. **Preview before up** — always preview, review diff, then apply
