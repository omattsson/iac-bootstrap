# IaC Bootstrap — AI Agent Customizations for Infrastructure-as-Code

Generate AI agent customizations (workspace instructions, agents, skills, file-scoped rules) for any Terraform infrastructure workspace. Works with **VS Code Copilot** and **Claude Code**.

The bootstrap process scans your IaC workspace, interviews you about conventions, compares against [battle-tested best practices](references/iac-best-practices.md), and generates tool-specific configuration files.

## What You Get

| Area | VS Code Copilot | Claude Code |
|------|-----------------|-------------|
| **Workspace instructions** | `.github/copilot-instructions.md` | `CLAUDE.md` |
| **Planning agent** | `.github/agents/infra-architect.agent.md` | Embedded in `CLAUDE.md` |
| **Module builder agent** | `.github/agents/terraform-module-builder.agent.md` | Embedded in `CLAUDE.md` |
| **Test writer agent** | `.github/agents/terraform-test-writer.agent.md` | Embedded in `CLAUDE.md` |
| **Orchestration agent** | `.github/agents/*-stack-manager.agent.md` | Embedded in `CLAUDE.md` |
| **File-scoped standards** | `.github/instructions/*.instructions.md` | Rules section in `CLAUDE.md` |
| **Module scaffolding** | `.github/skills/create-terraform-module/SKILL.md` | `.claude/commands/create-terraform-module.md` |
| **Stack management** | `.github/skills/create-*-stack/SKILL.md` | `.claude/commands/create-orchestration-stack.md` |
| **Pipeline generation** | `.github/skills/create-infra-pipeline/SKILL.md` | `.claude/commands/create-infra-pipeline.md` |

## Quick Start

### VS Code Copilot

**Option A — User-level skill (available in all workspaces):**

```bash
# Clone the repo (replace with your fork URL)
git clone https://github.com/omattsson/iac-bootstrap.git ~/git/iac-bootstrap

# Symlink as a Copilot skill
ln -s ~/git/iac-bootstrap ~/.copilot/skills/bootstrap-infra-workspace
```

Then in any IaC workspace, ask Copilot:

> Use the bootstrap-infra-workspace skill to set up AI agent customizations for this workspace.

**Option B — One-time use with `@workspace`:**

Open this repo alongside your IaC workspace in VS Code, then ask Copilot to follow the procedure in `SKILL.md` against your IaC workspace.

### Claude Code

```bash
# Clone the repo (replace with your fork URL)
git clone https://github.com/omattsson/iac-bootstrap.git ~/git/iac-bootstrap

# In your IaC workspace, run the bootstrap command
cd ~/my-iac-workspace
claude --prompt "Follow the bootstrap procedure from ~/git/iac-bootstrap/SKILL.md to generate Claude Code customizations for this workspace. Use the Claude Code templates from ~/git/iac-bootstrap/references/claude/ as the base."
```

Or copy the bootstrap command into your workspace:

```bash
mkdir -p .claude/commands
cp ~/git/iac-bootstrap/.claude/commands/bootstrap.md .claude/commands/
# Then use: /project:bootstrap
```

## Repository Structure

```
├── SKILL.md                              # Bootstrap procedure (Copilot skill entry point)
├── CLAUDE.md                             # Instructions for using this repo with Claude Code
├── .claude/commands/
│   └── bootstrap.md                      # Bootstrap as a Claude Code slash command
│
├── tools/
│   └── detect-smells.sh                  # IaC code smell detector (8 anti-pattern checks)
│
├── references/
│   ├── iac-best-practices.md             # Universal IaC patterns (10 categories)
│   │
│   ├── copilot/                          # VS Code Copilot output templates
│   │   ├── copilot-instructions.md.tmpl
│   │   ├── agents/
│   │   │   ├── infra-architect.agent.md.tmpl
│   │   │   ├── terraform-module-builder.agent.md.tmpl
│   │   │   ├── terraform-test-writer.agent.md.tmpl
│   │   │   └── orchestration-stack-manager.agent.md.tmpl
│   │   ├── skills/
│   │   │   ├── create-terraform-module.skill.md.tmpl
│   │   │   ├── create-orchestration-stack.skill.md.tmpl
│   │   │   └── create-infra-pipeline.skill.md.tmpl
│   │   └── instructions/
│   │       ├── iac-best-practices.instructions.md.tmpl
│   │       ├── terraform-modules.instructions.md.tmpl
│   │       ├── terraform-tests.instructions.md.tmpl
│   │       ├── orchestration-configs.instructions.md.tmpl
│   │       └── pipeline-templates.instructions.md.tmpl
│   │
│   └── claude/                           # Claude Code output templates
│       ├── CLAUDE.md.tmpl                # Combined instructions + rules
│       └── commands/
│           ├── create-terraform-module.md.tmpl
│           ├── create-orchestration-stack.md.tmpl
│           └── create-infra-pipeline.md.tmpl
│
└── examples/
    └── azure-terragrunt/                 # Complete example for Azure + Terragrunt
        ├── .github/                      # Copilot output
        │   ├── copilot-instructions.md
        │   ├── agents/
        │   │   ├── infra-architect.agent.md
        │   │   ├── terraform-module-builder.agent.md
        │   │   ├── terraform-test-writer.agent.md
        │   │   └── terragrunt-stack-manager.agent.md
        │   ├── skills/
        │   │   ├── create-terraform-module/SKILL.md
        │   │   ├── create-terragrunt-stack/SKILL.md
        │   │   └── create-infra-pipeline/SKILL.md
        │   └── instructions/
        │       ├── terraform-modules.instructions.md
        │       ├── terraform-tests.instructions.md
        │       ├── terragrunt-configs.instructions.md
        │       └── pipeline-templates.instructions.md
        ├── CLAUDE.md                     # Claude Code output
        └── .claude/commands/
            ├── create-terraform-module.md
            ├── create-terragrunt-stack.md
            └── create-infra-pipeline.md
```

## Code Smell Detector

[`tools/detect-smells.sh`](tools/detect-smells.sh) scans a Terraform workspace for common anti-patterns and prints each finding with a relevant location (file or module directory), including a line number when available.

```bash
bash tools/detect-smells.sh /path/to/your-iac-workspace
```

**8 checks, each reporting `SMELL` or `PASS`:**

| ID | Anti-Pattern |
|----|--------------|
| `hardcoded-secrets` | Credential-like keys assigned bare string literals in `.tf` / `.hcl` |
| `missing-tests` | Modules with resources but no `.tftest.hcl` or `*_test.go` |
| `monolithic-module` | Single module directory with ≥ 10 resource blocks |
| `missing-backend` | No `backend` or Terraform Cloud block anywhere |
| `no-tagging-standard` | Resource-containing modules with no `tags` or `labels` usage |
| `duplicated-code` | Identical canonical `.tf` files in different directories |
| `missing-provider-version` | Providers in `required_providers` without a `version` constraint |
| `missing-gitignore` | Missing `.gitignore` or missing `.terraform/` / `*.tfstate` entries |

The bootstrap procedure runs this detector automatically during Phase 3 (Gap Analysis) so findings appear alongside the high-level best-practices report.

## Best Practices Reference

The [IaC Best Practices](references/iac-best-practices.md) document covers 10 categories of proven patterns:

1. **Module Design** — single-responsibility, file layout, naming, full-name overrides
2. **Naming & Tagging** — sanitization, merge strategy, required tags
3. **Variable Design** — common vars, `optional()`, feature toggles
4. **Testing** — plan-only, mock providers, test organization
5. **Orchestration** — DRY hierarchy, dependencies, version pinning
6. **CI/CD** — plan→approve→apply, drift detection, identity-based auth
7. **Security** — no secrets, private by default, least privilege
8. **Code Quality** — pre-commit hooks, formatting, documentation
9. **State Management** — remote state, per-component state, encryption
10. **Progressive Rollout** — env promotion, blast radius, `prevent_destroy`

During bootstrap, the agent compares your workspace against these practices and reports gaps before generating files.

## Template Placeholders

All `.tmpl` files use `{{PLACEHOLDER}}` syntax. The bootstrap procedure replaces these with values discovered from your workspace or provided in the interview. Common placeholders:

### Core placeholders (used across most templates)

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{COMPANY_NAME}}` | Acme Corp | Organization name |
| `{{CLOUD_PROVIDER}}` | Azure | Primary cloud (Azure, AWS, GCP) |
| `{{MODULE_PREFIX}}` | tf-module | Module directory prefix |
| `{{ORCHESTRATION_TOOL}}` | Terragrunt | Orchestration tool name |
| `{{ORCHESTRATION_TOOL_LOWER}}` | terragrunt | Lowercase form for CLI commands |
| `{{ORCHESTRATION_DIR}}` | infrastructure-config | Directory containing orchestration configs |
| `{{CI_CD_PLATFORM}}` | GitHub Actions | CI/CD platform |
| `{{PROVIDER_NAME}}` | azurerm | Terraform provider name |
| `{{RESOURCE_IDENTIFIER}}` | default | Standard resource identifier (e.g., `azurerm_key_vault.default`) |
| `{{COMMON_VARS_FILE}}` | common.variables.tf | Shared variables filename |

### Naming & tagging placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{NAMING_PATTERN_HCL}}` | `"${var.prefix}-kv-${local.suffix}"` | HCL naming expression for `locals.tf` |
| `{{NAMING_LOCALS}}` | `name = substr(...)` | Full locals block for name construction |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_tags, var.tags)` | Tag merge expression |
| `{{TAG_MERGE_LOCAL}}` | `tags = merge(var.env_default_tags, var.tags)` | Full locals line for tag merging |

### Module & provider placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{MODULE_SOURCE_PATTERN}}` | `git::https://github.com/org/tf-module-{name}?ref={tag}` | Module source URL pattern |
| `{{VERSION_TAG_LOCATION}}` | `subscription.hcl` → `module_tags` | Where module version pins are stored |
| `{{PROVIDER_BLOCK}}` | `azurerm = { source = "hashicorp/azurerm", ... }` | Provider block for `versions.tf` |
| `{{PROVIDER_VERSION_CONSTRAINTS}}` | `>=4.21.0,<5.0` | Provider version constraint |
| `{{PROVIDER_RESOURCE_EXAMPLE}}` | `azurerm_key_vault.default` | Example resource reference |
| `{{LOCATION_ATTRIBUTE}}` | `location = var.location` | Resource location attribute |
| `{{RESOURCE_GROUP_ATTRIBUTE}}` | `resource_group_name = var.resource_group_name` | Resource group attribute |

### Orchestration placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{ENVCOMMON_PATTERN}}` | `_envcommon/*.hcl` | Shared config pattern/path |
| `{{HIERARCHY_DIAGRAM}}` | (multi-line tree) | ASCII hierarchy diagram |
| `{{HIERARCHY_FILES_DESCRIPTION}}` | (multi-line) | Description of each hierarchy file |
| `{{COMPONENT_CONFIG_PATTERN}}` | (HCL block) | Template for component configs |
| `{{ENVCOMMON_TEMPLATE}}` | (HCL block) | Template for shared configs |
| `{{MOCK_OUTPUTS_EXAMPLE}}` | (HCL block) | Example mock_outputs block |
| `{{VALIDATE_COMMAND}}` | `terragrunt validate` | Validation command |
| `{{PLAN_COMMAND}}` | `terragrunt plan` | Plan command |

### Variable & testing placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{STANDARD_VARIABLES}}` | (bullet list) | All cross-module variables |
| `{{TEST_STANDARD_VARIABLES}}` | (HCL variables block) | Standard vars for test files |
| `{{DATA_SOURCE_OVERRIDE}}` | `override_data { target = data.azurerm_subscription.current ... }` | Mock data sources in tests |
| `{{OPTIONAL_FEATURES}}` | private endpoints, diagnostics, RBAC | Optional module features |
| `{{EXPECTED_NAME_PATTERN}}` | `test-auto-kv-mysuffix` | Expected name in test assertions |

### CI/CD placeholders

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{PIPELINE_APPLY_TO}}` | `**/pipelines/**/*.yml` | Glob for pipeline files |
| `{{AUTH_PATTERN}}` | (multi-line) | Authentication config block |
| `{{AUTH_REQUIREMENTS}}` | (multi-line) | Auth requirements description |
| `{{SINGLE_COMPONENT_PIPELINE}}` | (YAML block) | Single component pipeline template |
| `{{STACK_PIPELINE}}` | (YAML block) | Full stack pipeline template |
| `{{DRIFT_PIPELINE}}` | (YAML block) | Drift detection pipeline template |
| `{{STANDARD_PARAMETERS}}` | (multi-line) | Pipeline parameter definitions |
| `{{PIPELINE_CONVENTIONS}}` | (multi-line) | Pipeline naming/structure conventions |

## Contributing

1. Fork the repo
2. Add/modify templates in `references/`
3. Update `SKILL.md` if the procedure changes
4. Test by running the bootstrap against a real workspace
5. Submit a PR

## License

MIT
