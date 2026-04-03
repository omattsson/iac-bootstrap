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
# Clone the repo
git clone https://github.com/YOUR_ORG/copilot-iac-bootstrap.git ~/git/copilot-iac-bootstrap

# Symlink as a Copilot skill
ln -s ~/git/copilot-iac-bootstrap ~/.copilot/skills/bootstrap-infra-workspace
```

Then in any IaC workspace, ask Copilot:

> Use the bootstrap-infra-workspace skill to set up AI agent customizations for this workspace.

**Option B — One-time use with `@workspace`:**

Open this repo alongside your IaC workspace in VS Code, then ask Copilot to follow the procedure in `SKILL.md` against your IaC workspace.

### Claude Code

```bash
# Clone the repo
git clone https://github.com/YOUR_ORG/copilot-iac-bootstrap.git ~/git/copilot-iac-bootstrap

# In your IaC workspace, run the bootstrap command
cd ~/my-iac-workspace
claude --prompt "Follow the bootstrap procedure from ~/git/copilot-iac-bootstrap/SKILL.md to generate Claude Code customizations for this workspace. Use the Claude Code templates from ~/git/copilot-iac-bootstrap/references/claude/ as the base."
```

Or copy the bootstrap command into your workspace:

```bash
mkdir -p .claude/commands
cp ~/git/copilot-iac-bootstrap/.claude/commands/bootstrap.md .claude/commands/
# Then use: /project:bootstrap
```

## Repository Structure

```
├── SKILL.md                              # Bootstrap procedure (Copilot skill entry point)
├── CLAUDE.md                             # Instructions for using this repo with Claude Code
├── .claude/commands/
│   └── bootstrap.md                      # Bootstrap as a Claude Code slash command
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
        └── CLAUDE.md                     # Claude Code output
```

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

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{COMPANY_NAME}}` | Acme Corp | Organization name |
| `{{CLOUD_PROVIDER}}` | Azure | Primary cloud (Azure, AWS, GCP) |
| `{{MODULE_PREFIX}}` | tf-module | Module directory prefix |
| `{{ORCHESTRATION_TOOL}}` | Terragrunt | Orchestration tool name |
| `{{CI_CD_PLATFORM}}` | GitHub Actions | CI/CD platform |
| `{{PROVIDER_NAME}}` | azurerm | Terraform provider name |
| `{{RESOURCE_IDENTIFIER}}` | default | Standard resource identifier |
| `{{NAMING_PATTERN_HCL}}` | `"${var.prefix}-kv-${local.suffix}"` | HCL naming expression |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_tags, var.tags)` | Tag merge expression |

See individual template files for the full list of placeholders they expect.

## Contributing

1. Fork the repo
2. Add/modify templates in `references/`
3. Update `SKILL.md` if the procedure changes
4. Test by running the bootstrap against a real workspace
5. Submit a PR

## License

MIT
