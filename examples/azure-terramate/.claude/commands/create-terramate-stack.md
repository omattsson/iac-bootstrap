# Create Terramate Stack/Component

Create or extend Terramate configurations for the Contoso infrastructure workspace.

## Usage
Describe what to add: `$ARGUMENTS`

If unclear, ask:
- Adding a new stack, a new environment, or updating shared generated config?
- Which Terraform module does the stack deploy?
- Does it depend on outputs from another stack?

## Hierarchy

```
infrastructure-config/
  globals.tm.hcl                        ← org-wide defaults
  _generate/                            ← shared generate_hcl blocks
  {environment}/
    globals.tm.hcl                      ← env: name, location, subscription_id
    {stack}/
      globals.tm.hcl                    ← stack: prefix, service name
      stack.tm.hcl                      ← stack identity and ordering
      {component}.tf                    ← hand-written module call
      _generated_backend.tf             ← generated (do not edit)
      _generated_provider.tf            ← generated (do not edit)
```

## Task A: Add a New Stack

### 1. Create `stack.tm.hcl`
```hcl
stack {
  name        = "{service}-{environment}"
  description = "Manages {description} in {environment}"
  id          = "{service}-{environment}-weu"
  after       = ["../networking"]
}
```

### 2. Create stack globals (`globals.tm.hcl`)
```hcl
globals {
  prefix       = "app-weu-{env}"
  service_name = "{service}"
}
```

### 3. Add module version to root globals
In `infrastructure-config/globals.tm.hcl` → `module_versions`:
```hcl
"{new-module}" = "v1.0.0"
```

### 4. Create the module call (`{component}.tf`)
```hcl
module "{name}" {
  source = "git::https://dev.azure.com/contoso/infra/_git/tf-module-{name}?ref=${global.module_versions["{name}"]}"

  prefix              = global.prefix
  location            = global.location
  resource_group_name = var.resource_group_name
  tags                = {}
  env_default_tags    = {
    environment = global.environment
    managed_by  = "Terraform"
    product     = global.service_name
  }
}
```

### 5. Regenerate
```bash
terramate generate
```
Review the diff — only new `_generated_*.tf` files should appear.

## Task B: Add a New Environment

### 1. Create `infrastructure-config/{env}/globals.tm.hcl`
```hcl
globals {
  environment     = "{env}"
  location        = "westeurope"
  subscription_id = "YOUR-SUBSCRIPTION-ID"
}
```

### 2. Copy stack dirs from sibling environment and update globals

## Cross-Stack Reference

```hcl
data "terraform_remote_state" "networking" {
  backend = "azurerm"
  config = {
    resource_group_name  = "rg-tfstate-weu"
    storage_account_name = "contosotfstateweu"
    container_name       = "tfstate"
    key                  = "{environment}/networking/terraform.tfstate"
  }
  defaults = {
    vnet_id = "/subscriptions/mock/resourceGroups/mock/providers/Microsoft.Network/virtualNetworks/mock"
  }
}
```

## Validation

```bash
terramate validate
terramate run --changed terraform plan
```

Check: module version in root globals, `terramate generate` clean diff, unique stack ID.
