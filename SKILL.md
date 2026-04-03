---
name: bootstrap-infra-workspace
description: "Bootstrap a Terraform infrastructure workspace with AI agent customizations for VS Code Copilot and/or Claude Code. Use when: setting up a new IaC workspace, onboarding a company to AI-assisted infra automation, running IaC maturity assessments, generating copilot instructions, agents, skills, and file-specific instructions from templates."
argument-hint: "Describe the workspace: cloud provider, module structure, orchestration tool"
---

# Bootstrap Infrastructure Workspace

Generates a complete set of AI agent customizations for a Terraform infrastructure workspace. Supports output for **VS Code Copilot** (`.github/` files) and **Claude Code** (`CLAUDE.md` + `.claude/commands/`).

All templates are parameterized and adapted to the target company's conventions. A best practices gap analysis is run before generating files.

## When to Use
- Setting up a new infrastructure-as-code workspace with AI assistance
- Onboarding a company's existing IaC repos to use AI agents effectively
- Migrating AI customizations from one workspace to another
- Starting fresh with best-practice agent/skill templates for infra work
- Running an IaC maturity assessment against proven patterns
- Improving an existing workspace's practices based on battle-tested conventions

## Procedure

### Phase 1: Discovery

Explore the target workspace to understand existing patterns:

1. **Scan for Terraform modules**: `file_search("**/main.tf")` or `file_search("**/versions.tf")`
2. **Scan for orchestration configs**: `file_search("**/terragrunt.hcl")`, `file_search("**/root.hcl")`, `file_search("**/terramate.tm.hcl")`
3. **Scan for CI/CD pipelines**: `file_search("**/*.yml")` in pipeline directories
4. **Check for existing customizations**: `file_search("**/.github/copilot-instructions.md")`, `file_search("**/CLAUDE.md")`

Build a profile of the workspace by reading representative files.

### Phase 2: Interview

Gather what can't be inferred from code:

```
Questions:
1.  Company/org name — used in descriptions and comments
2.  Cloud provider(s) — Azure, AWS, GCP, or multi-cloud
3.  Module source pattern — Git URL pattern for module sourcing
4.  Module prefix — directory naming (e.g., tf-module-*, terraform-aws-*, modules/)
5.  Orchestration tool — Terragrunt, Terramate, plain Terraform workspaces, or none
6.  CI/CD platform — GitHub Actions, Azure DevOps, GitLab CI, Atlantis
7.  Auth pattern — Managed Identity, OIDC, service principal, IAM roles
8.  State backend — Azure Blob, S3, GCS, Terraform Cloud
9.  Naming convention — how resources are named (prefix-type-suffix, etc.)
10. Tag/label standard — required tags and merge strategy
11. Test framework — native terraform test, Terratest, checkov, tflint, OPA/Rego, or a combination
12. Standard variables — cross-module variables that all modules receive
13. Target tool(s) — VS Code Copilot, Claude Code, or both
```

### Phase 3: Best Practices Gap Analysis

Before generating files, compare the workspace's current patterns against the [IaC Best Practices](./references/iac-best-practices.md) reference.

Evaluate and report on:

| Area | What to Check |
|------|---------------|
| **Module design** | Consistent file layout? Resource identifier convention? Full-name overrides? Name length safety? |
| **Naming & tagging** | Name sanitization? Tag merge strategy documented? Required tags enforced? |
| **Variable design** | Common variables file? `optional()` with defaults? Feature toggles via count/for_each? |
| **Testing** | Plan-only tests? Mock providers? One file per concern? All common vars included? |
| **Orchestration** | DRY hierarchy? Explicit dependencies with mock outputs? Version pinning per env? |
| **CI/CD** | Plan→approve→apply flow? Drift detection? Identity-based auth? Provider caching? |
| **Security** | No hardcoded secrets? Private by default? Private endpoint pattern? Least privilege? |
| **Code quality** | Pre-commit hooks? `terraform fmt`? Auto-generated docs? Backward compatibility? |
| **State management** | Remote state? One state per component? Encryption at rest? |
| **Progressive rollout** | Env promotion pattern? Blast radius reduction? `prevent_destroy` on critical resources? |

For each area, classify as:
- **Adopted** — already follows the practice
- **Partial** — some modules/configs follow it, others don't
- **Missing** — not implemented yet
- **N/A** — not applicable to this workspace

Present findings as a table, then ask the user which gaps to address. Incorporate the relevant practices into the generated customization files.

### Phase 4: Generate Files

Based on discovery + interview answers, generate customization files using templates from this repo. Templates use `{{PLACEHOLDER}}` syntax — replace all placeholders with actual values.

#### For VS Code Copilot — use templates from [./references/copilot/](./references/copilot/):

| Output File | Template |
|-------------|----------|
| `.github/copilot-instructions.md` | `copilot/copilot-instructions.md.tmpl` |
| `.github/agents/infra-architect.agent.md` | `copilot/agents/infra-architect.agent.md.tmpl` |
| `.github/agents/terraform-module-builder.agent.md` | `copilot/agents/terraform-module-builder.agent.md.tmpl` |
| `.github/agents/terraform-test-writer.agent.md` | `copilot/agents/terraform-test-writer.agent.md.tmpl` |
| `.github/agents/*-stack-manager.agent.md` | `copilot/agents/orchestration-stack-manager.agent.md.tmpl` |
| `.github/skills/create-terraform-module/SKILL.md` | `copilot/skills/create-terraform-module.skill.md.tmpl` |
| `.github/skills/create-*-stack/SKILL.md` | `copilot/skills/create-orchestration-stack.skill.md.tmpl` |
| `.github/skills/create-infra-pipeline/SKILL.md` | `copilot/skills/create-infra-pipeline.skill.md.tmpl` |
| `.github/instructions/terraform-modules.instructions.md` | `copilot/instructions/terraform-modules.instructions.md.tmpl` |
| `.github/instructions/terraform-tests.instructions.md` | `copilot/instructions/terraform-tests.instructions.md.tmpl` |
| `.github/instructions/terratest.instructions.md` *(if Terratest used)* | `copilot/instructions/terratest.instructions.md.tmpl` |
| `.github/instructions/checkov.instructions.md` *(if custom checkov checks)* | `copilot/instructions/checkov.instructions.md.tmpl` |
| `.github/instructions/tflint.instructions.md` *(if custom tflint rules)* | `copilot/instructions/tflint.instructions.md.tmpl` |
| `.github/instructions/opa.instructions.md` *(if OPA/Rego policies)* | `copilot/instructions/opa.instructions.md.tmpl` |
| `.github/instructions/*-configs.instructions.md` | `copilot/instructions/orchestration-configs.instructions.md.tmpl` |
| `.github/instructions/pipeline-templates.instructions.md` | `copilot/instructions/pipeline-templates.instructions.md.tmpl` |

#### For Claude Code — use templates from [./references/claude/](./references/claude/):

| Output File | Template |
|-------------|----------|
| `CLAUDE.md` | `claude/CLAUDE.md.tmpl` |
| `.claude/commands/create-terraform-module.md` | `claude/commands/create-terraform-module.md.tmpl` |
| `.claude/commands/create-orchestration-stack.md` | `claude/commands/create-orchestration-stack.md.tmpl` |
| `.claude/commands/create-infra-pipeline.md` | `claude/commands/create-infra-pipeline.md.tmpl` |

#### Generation rules:
1. Only generate orchestration files if the workspace uses Terragrunt/Terramate/etc.
2. Adapt CI/CD templates to the actual platform (GitHub Actions/ADO/GitLab)
3. Adapt provider references to the actual cloud (azurerm/aws/google)
4. Use actual module source URLs, not placeholders
5. Include real naming patterns discovered from the workspace
6. Skip files that already exist (warn and offer to merge)
7. If generating for both tools, ensure consistency between Copilot and Claude outputs
8. Generate framework-specific instruction files only for frameworks the workspace actually uses (from interview question 11)

### Phase 5: Validate

After generating:
1. Verify all `description` fields are keyword-rich for discovery
2. For Copilot: check `applyTo` patterns match actual file paths
3. For Claude: verify CLAUDE.md is self-contained (no broken references)
4. Confirm no hardcoded secrets leaked into outputs
5. Review agent tool lists — minimize to what's needed per role

## Template References

- [IaC Best Practices](./references/iac-best-practices.md) — Universal patterns for gap analysis
- [Copilot Templates](./references/copilot/) — VS Code Copilot output templates
- [Claude Templates](./references/claude/) — Claude Code output templates
