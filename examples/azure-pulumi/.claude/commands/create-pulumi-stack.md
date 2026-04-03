# Create Pulumi Stack/Component

Create or extend Pulumi Python programs for the Contoso Azure infrastructure.

## Usage
Describe what to add: `$ARGUMENTS`

If unclear, ask:
- Adding a resource to an existing stack, or creating a new stack?
- Which cloud resource or shared ComponentResource does it involve?
- Does it consume outputs from another stack (networking, security)?

## Hierarchy

```
infra/
  components/                   ← shared ComponentResource classes
  networking/                   ← deployed first
  security/                     ← depends on networking
  app/                          ← depends on networking + security
```

## Task A: Add a New Resource

### 1. Check `infra/components/` for a matching ComponentResource

### 2. Import and instantiate in `__main__.py`
```python
from components.{name} import {Name}Component

cfg = pulumi.Config("contoso")
env = cfg.require("environment")
default_tags = {"environment": env, "managed_by": "Pulumi", "product": "{product}"}

resource = {Name}Component("{name}", {
    "resource_group_name": cfg.require("resourceGroupName"),
    "location": cfg.require("azure-native:location"),
    "tenant_id": cfg.require("tenantId"),
    "default_tags": default_tags,
})

pulumi.export("{name}_id", resource.{primary_resource}.id)
```

### 3. Preview
```bash
pulumi preview --stack dev
```

## Task B: Create a New Stack

### 1. `Pulumi.yaml`
```yaml
name: contoso-{stack-name}
runtime: python
description: "{Description}"
```

### 2. `Pulumi.dev.yaml`
```yaml
config:
  azure-native:location: westeurope
  contoso:environment: "dev"
  contoso:prefix: "app-weu-dev"
  contoso:resourceGroupName: "rg-{stack}-dev-weu"
  contoso:tenantId: "00000000-0000-0000-0000-000000000000"
```

### 3. Set secrets
```bash
pulumi config set --secret --stack dev contoso:clientSecret <value>
```

### 4. `requirements.txt`
```
pulumi>=3.0.0,<4.0.0
pulumi-azure-native>=2.0.0,<3.0.0
```

## Task C: Add a Shared ComponentResource

Create `infra/components/{name}.py`:
```python
import pulumi
import pulumi_azure_native as azure

class {Name}Component(pulumi.ComponentResource):
    def __init__(self, name: str, args: dict, opts: pulumi.ResourceOptions | None = None):
        super().__init__("contoso:components:{Name}", name, {}, opts)
        child_opts = pulumi.ResourceOptions(parent=self)
        # create resources with child_opts
        self.register_outputs({...})
```

## Cross-Stack Reference

```python
networking = pulumi.StackReference(f"contoso/networking/{env}")
vnet_id = networking.get_output("vnet_id")
# Handle None for plan-time safety:
subnet_id = networking.get_output("subnets").apply(
    lambda s: (s or {}).get("default", "/subscriptions/mock/subnets/default")
)
```

## Validation

```bash
pulumi preview --stack dev
pulumi up --stack dev --yes
```

Check: all config keys set, stack references safe for preview, no hardcoded secrets, outputs exported.
