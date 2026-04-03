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

Explore the target workspace to understand existing patterns and auto-populate interview answers.

#### 1a. Structural scan

1. **Scan for Terraform modules**: `file_search("**/main.tf")` or `file_search("**/versions.tf")`
2. **Scan for orchestration configs**: `file_search("**/terragrunt.hcl")`, `file_search("**/root.hcl")`, `file_search("**/terramate.tm.hcl")`
3. **Scan for CI/CD pipelines**: `file_search("**/*.yml")` in pipeline directories
4. **Check for existing customizations**: `file_search("**/.github/copilot-instructions.md")`, `file_search("**/CLAUDE.md")`

#### 1b. Auto-detection heuristics

Run the following checks and record each detected value. Mark each answer as **detected**, **ambiguous** (multiple candidates found), or **unknown** (no signal found).

| Interview Q# | What to detect | How to detect |
|---|---|---|
| **Q2 — Cloud provider** | Azure / AWS / GCP / multi-cloud | Search `**/*.tf` for `provider "azurerm"` → Azure; `provider "aws"` → AWS; `provider "google"` → GCP. If exactly one provider family is found → mark as that cloud. If two or more distinct provider families are found → mark as multi-cloud (not ambiguous). |
| **Q3 — Module source pattern** | Git URL template for `source =` | Grep `**/*.tf` and `**/*.hcl` for `source\s*=\s*"git::` lines; extract the base URL and tag-ref pattern. If all occurrences share the same base URL → detected. If multiple distinct base URLs are found → mark as ambiguous and list all candidates. |
| **Q4 — Module prefix** | Directory prefix used for modules | List directories within the workspace root that match `tf-module-*`, `terraform-*`, `modules/`, or similar. Do not look outside the workspace root. If all matching directories share a common prefix → detected. If no match → unknown. |
| **Q5 — Orchestration tool** | Terragrunt / Terramate / workspaces / none | `file_search("**/terragrunt.hcl")` → Terragrunt; `file_search("**/*.tm.hcl")` → Terramate; `file_search("**/*.tfworkspace")` or `terraform workspace list` output in docs → Workspaces. |
| **Q6 — CI/CD platform** | GitHub Actions / Azure DevOps / GitLab CI / Atlantis | `file_search(".github/workflows/*.yml")` → GitHub Actions; `file_search("azure-pipelines*.yml")` or `azure-pipelines/` dir → Azure DevOps; `file_search(".gitlab-ci.yml")` → GitLab CI; `file_search("atlantis.yaml")` → Atlantis. |
| **Q7 — Auth pattern** | Managed Identity / OIDC / service principal / IAM roles | In provider blocks, look for `use_msi = true` or `use_cli = true` → Managed Identity; `use_oidc = true` or `oidc_*` attributes → OIDC; `client_id` + `client_secret` env refs → Service Principal; `assume_role` or `web_identity_token_file` → IAM/OIDC (AWS). |
| **Q8 — State backend** | Azure Blob / S3 / GCS / Terraform Cloud | Search `**/*.tf` and `**/*.hcl` for `backend "azurerm"` → Azure Blob; `backend "s3"` → S3; `backend "gcs"` → GCS; `backend "remote"` or `cloud {}` → Terraform Cloud. |
| **Q9 — Naming convention** | Naming pattern expression | Read `locals.tf` in each discovered module; look for name construction expressions (e.g., `"${var.prefix}-kv-${local.suffix}"`). If all modules use the same pattern → detected. If patterns differ across modules → mark as ambiguous and list the most common pattern plus any outliers. |
| **Q11 — Test framework** | Native tftest / Terratest / both | `file_search("**/*.tftest.hcl")` → native terraform test; `file_search("**/*_test.go")` → Terratest; both present → both. |

#### 1c. Build workspace profile

After running the checks, compile a workspace profile:

```
Workspace profile (auto-detected):
  Cloud provider:      <value or UNKNOWN>
  Module prefix:       <value or UNKNOWN>
  Module source URL:   <value or UNKNOWN>
  Orchestration tool:  <value or UNKNOWN>
  CI/CD platform:      <value or UNKNOWN>
  Auth pattern:        <value or UNKNOWN>
  State backend:       <value or UNKNOWN>
  Naming pattern:      <value or UNKNOWN>
  Test framework:      <value or UNKNOWN>
```

### Phase 2: Interview

Present the auto-detected answers to the user for confirmation, then ask only for the answers that are **unknown** or **ambiguous**. Format the pre-filled answers as a numbered list matching the original question order, with detected values shown inline so the user can confirm or override each one.

**Pre-fill confirmation block (always present):**

```
Based on scanning your workspace, I've pre-filled the following answers.
Please confirm each one or type a correction (press Enter to accept):

2.  Cloud provider(s):     <detected value, or "unknown — please provide">
3.  Module source pattern: <detected value, or "unknown — please provide">
4.  Module prefix:         <detected value, or "unknown — please provide">
5.  Orchestration tool:    <detected value, or "unknown — please provide">
6.  CI/CD platform:        <detected value, or "unknown — please provide">
7.  Auth pattern:          <detected value, or "unknown — please provide">
8.  State backend:         <detected value, or "unknown — please provide">
9.  Naming convention:     <detected value, or "unknown — please provide">
11. Test framework:        <detected value, or "unknown — please provide">
```

**Then ask only the unanswered questions:**

```
Still need your input for:
1.  Company/org name — used in descriptions and comments
10. Tag/label standard — required tags and merge strategy (e.g., managed_by, environment, product)
12. Standard variables — cross-module variables that all modules receive
13. Target tool(s) — VS Code Copilot, Claude Code, or both
    (plus any of Q2–Q11 marked as ambiguous or overridden by you above)
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
