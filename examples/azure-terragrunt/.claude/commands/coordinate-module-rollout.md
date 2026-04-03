# Coordinate Module Rollout

Plan and guide a cross-repo module change across the full chain: **module code → version tag → orchestration config → pipeline**.

## Usage
Provide the module name and new tag as the argument: `$ARGUMENTS`

If no argument is given, ask:
- Which module is changing? (e.g., `tf-module-key-vault`)
- What is the new version tag?
- Is this a breaking change, an additive change, or non-breaking?

## Workflow

### Step 1 — Discover downstream consumers

Search `infrastructure-config/` for all references to the module:

```bash
grep -r "tf-module-{name}" infrastructure-config/ --include="*.hcl" -l
```

For each match, record:
- Environment (e.g., `dev`, `staging`, `prod`)
- Stack and component path
- Current pinned tag in `subscription.hcl` → `module_tags`

### Step 2 — Classify the change

| Classification | Definition | Consumer action |
|----------------|-----------|-----------------|
| **Non-breaking** | No output/variable removals or renames | Bump `module_tags` only |
| **Additive** | New optional variables or outputs added | Bump tag; consumers may opt in |
| **Breaking** | Removed/renamed outputs or required variables | Update `_envcommon/*.hcl` `inputs` and `mock_outputs` first |

### Step 3 — Plan version bumps

For each consumer environment, update `subscription.hcl` → `module_tags`:

```hcl
locals {
  module_tags = {
    # ... other modules ...
    {name} = "{new_tag}"
  }
}
```

Roll out progressively: **dev → staging → prod**.

### Step 4 — Validate each environment before proceeding

After each version bump:

```bash
terragrunt validate
terragrunt plan
```

Review plan output for unexpected changes (especially destroys) before moving to the next environment.

### Step 5 — Identify and trigger Azure DevOps pipelines

List pipelines in `iac-pipeline-templates/` that deploy the affected stacks. Trigger in dependency order (upstream stacks first — e.g., `resource-group` before `key-vault`). Insert manual approval gates between environments.

## Rollout Plan Template

```
## Rollout Plan: tf-module-{name} {old_tag} → {new_tag}

### Consumers
| Environment | Stack | Component | Config File | Current Tag |
|-------------|-------|-----------|-------------|-------------|

### Pre-conditions
- [ ] {Breaking change migration required in _envcommon files}

### Steps
1. Tag module repo: `git tag {new_tag} && git push origin {new_tag}`
2. Update `module_tags.{name}` in `config/dev/subscription.hcl`
3. Run: `terragrunt validate && terragrunt plan` — review output
4. Trigger dev pipeline in Azure DevOps — await green
5. Update `module_tags.{name}` in `config/staging/subscription.hcl`
6. Run: `terragrunt validate && terragrunt plan` — review output
7. Trigger staging pipeline — await green + approval
8. Update `module_tags.{name}` in `config/prod/subscription.hcl`
9. Run: `terragrunt validate && terragrunt plan` — review output
10. Trigger prod pipeline — await green + approval

### Rollback
- Revert `module_tags.{name}` in `subscription.hcl` to `{old_tag}`
- Re-run `terragrunt plan` + apply on affected environments
```

## Checklist

- [ ] All consumers identified in `infrastructure-config/`
- [ ] Change classified (non-breaking / additive / breaking)
- [ ] Breaking changes communicated — `_envcommon` inputs and `mock_outputs` updated
- [ ] Version bumped in dev — plan reviewed — no unexpected destroys
- [ ] Dev pipeline green
- [ ] Version bumped in staging — plan reviewed
- [ ] Staging pipeline green
- [ ] Version bumped in prod — plan reviewed
- [ ] Prod pipeline green
- [ ] Rollback procedure documented
