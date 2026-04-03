---
description: "Pulumi Python program and stack configuration standards. Use when writing or modifying Pulumi programs, Pulumi.yaml project files, stack config files, or ComponentResource classes."
applyTo: "infra/**"
---

# Pulumi Configuration Standards

## Project Layout
```
infra/{stack-name}/
  Pulumi.yaml                   # Project metadata (name, runtime)
  Pulumi.{environment}.yaml     # Stack-specific config (committed, non-secret values)
  __main__.py                   # Entry point: instantiate components, export outputs
  requirements.txt              # Pin dependencies with exact versions or compatible bounded ranges
infra/components/               # Shared ComponentResource classes (imported by stacks)
  key_vault.py
  networking.py
```

## Stack Config Pattern (`Pulumi.{env}.yaml`)
```yaml
config:
  azure-native:location: westeurope
  contoso:environment: "dev"
  contoso:prefix: "app-weu-dev"
  contoso:resourceGroupName: "rg-app-dev-weu"
  contoso:tenantId: "00000000-0000-0000-0000-000000000000"
  # Secrets are encrypted — set with: pulumi config set --secret contoso:clientSecret <value>
  # They appear as: contoso:clientSecret: secure: <ciphertext>
```

## ComponentResource Pattern
Every reusable resource group must be a `ComponentResource` in `infra/components/`:
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

        self.register_outputs({"vault_id": self.vault.id, "vault_uri": self.vault.properties.vault_uri})
```

## Naming Convention
`f"{prefix}-{abbreviation}-{suffix}"` with max-length enforcement.
Sanitize user inputs: `re.sub(r"[^0-9A-Za-z]+", "-", suffix).strip("-").lower()`
- Key Vault: max 24 chars — `(f"{prefix}-kv-{suffix}")[:24]`

## Tagging Standard
```python
tags = {**default_tags, **resource_tags}
# default_tags from config (environment, managed_by, product)
# resource_tags win on key conflicts
```
Required tags: `environment`, `managed_by: Pulumi`, `product`.

## Cross-Stack References
Use `pulumi.StackReference` to read outputs from other stacks:
```python
networking = pulumi.StackReference(f"contoso/networking/{env}")
vnet_id = networking.get_output("vnet_id")
# Always handle None for plan-time safety:
subnet_id = networking.get_output("subnets").apply(
    lambda s: (s or {}).get("default", "/subscriptions/mock/subnets/default")
)
```

## Secret Management
- Use `pulumi config set --secret contoso:<key> <value>` for sensitive values
- Read namespaced secrets with `pulumi.Config("contoso").require_secret("key")`
- State backend secret provider: Azure KeyVault (`azurekeyvault://contoso-pulumi-kv`)
- Never log or export secret values via `pulumi.export`

## State Backend
Pulumi service (or self-hosted): `PULUMI_BACKEND_URL=azblob://tfstate?storage_account=contosotfstateweu`

## Deployment Commands
- Preview: `pulumi preview --stack dev`
- Deploy: `pulumi up --stack dev --yes` (always preview first)
- Destroy: `pulumi destroy --stack dev` (requires explicit approval)
- Refresh: `pulumi refresh --stack dev` (sync state with Azure)
