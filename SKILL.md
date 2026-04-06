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
11. Test framework — native terraform test, Terratest, or both
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

#### Maturity Score Computation

After collecting all gap analysis classifications, compute an overall maturity score using the weighted model below:

| Category | Weight | Adopted | Partial | Missing |
|----------|--------|---------|---------|---------|
| Security | 20% | 20 pts | 10 pts | 0 pts |
| Testing | 15% | 15 pts | 7.5 pts | 0 pts |
| CI/CD | 15% | 15 pts | 7.5 pts | 0 pts |
| Module Design | 15% | 15 pts | 7.5 pts | 0 pts |
| Naming & Tagging | 10% | 10 pts | 5 pts | 0 pts |
| Variable Design | 5% | 5 pts | 2.5 pts | 0 pts |
| Orchestration | 5% | 5 pts | 2.5 pts | 0 pts |
| Code Quality | 5% | 5 pts | 2.5 pts | 0 pts |
| State Management | 5% | 5 pts | 2.5 pts | 0 pts |
| Progressive Rollout | 5% | 5 pts | 2.5 pts | 0 pts |

**For N/A categories:** exclude the category from the total and renormalize the remaining weights so they sum to 100%.

**Gap severity:**
- **Critical gap** — Any Missing category, or a Partial status in Security, Testing, or CI/CD (weight ≥ 15%)
- **Moderate gap** — Partial or Missing status in any category other than Security, Testing, or CI/CD (including Module Design at 15%)

#### Maturity Report Generation

Generate a maturity assessment report using the template at [./references/maturity-report.md.tmpl](./references/maturity-report.md.tmpl). Replace all `{{PLACEHOLDER}}` values with computed results and workspace-specific findings.

For each **critical gap** entry, include:
- Gap category as a subheading
- What was found (specific observation from the workspace)
- Risk if unaddressed
- Ordered remediation steps
- Estimated effort

For each **moderate gap** entry, include the category, what was found, and a brief remediation note.

For **strengths**, list each fully-adopted category with a one-sentence note on what the workspace does well.

For **recommended next actions**, provide 3–5 concrete, prioritized steps drawn from the critical and moderate gaps.

The report content is prepared during Phase 3 but written to disk during Phase 4 (see Generation rules).

### Phase 4: Generate Files

Based on discovery + interview answers, generate customization files using templates from this repo. Templates use `{{PLACEHOLDER}}` syntax — replace all placeholders with actual values.

#### For VS Code Copilot — use templates from [./references/copilot/](./references/copilot/):

Select the cloud-specific subdirectory first, then fall back to the base template for files not overridden:

| Cloud | Subdirectory |
|-------|-------------|
| **Azure** | `copilot/` (base templates) |
| **AWS** | `copilot/aws/` for overridden files, `copilot/` for the rest |
| **GCP** | `copilot/gcp/` for overridden files, `copilot/` for the rest |

| Output File | Azure Template | AWS Template | GCP Template |
|-------------|---------------|--------------|--------------|
| `.github/copilot-instructions.md` | `copilot/copilot-instructions.md.tmpl` | `copilot/aws/copilot-instructions.md.tmpl` | `copilot/gcp/copilot-instructions.md.tmpl` |
| `.github/agents/infra-architect.agent.md` | `copilot/agents/infra-architect.agent.md.tmpl` | ← same | ← same |
| `.github/agents/terraform-module-builder.agent.md` | `copilot/agents/terraform-module-builder.agent.md.tmpl` | `copilot/aws/agents/terraform-module-builder.agent.md.tmpl` | `copilot/gcp/agents/terraform-module-builder.agent.md.tmpl` |
| `.github/agents/terraform-test-writer.agent.md` | `copilot/agents/terraform-test-writer.agent.md.tmpl` | ← same | ← same |
| `.github/agents/*-stack-manager.agent.md` | `copilot/agents/orchestration-stack-manager.agent.md.tmpl` | ← same | ← same |
| `.github/skills/create-terraform-module/SKILL.md` | `copilot/skills/create-terraform-module.skill.md.tmpl` | `copilot/aws/skills/create-terraform-module.skill.md.tmpl` | `copilot/gcp/skills/create-terraform-module.skill.md.tmpl` |
| `.github/skills/create-*-stack/SKILL.md` | `copilot/skills/create-orchestration-stack.skill.md.tmpl` | ← same | ← same |
| `.github/skills/create-infra-pipeline/SKILL.md` | `copilot/skills/create-infra-pipeline.skill.md.tmpl` | ← same | ← same |
| `.github/instructions/terraform-modules.instructions.md` | `copilot/instructions/terraform-modules.instructions.md.tmpl` | `copilot/aws/instructions/terraform-modules.instructions.md.tmpl` | `copilot/gcp/instructions/terraform-modules.instructions.md.tmpl` |
| `.github/instructions/terraform-tests.instructions.md` | `copilot/instructions/terraform-tests.instructions.md.tmpl` | `copilot/aws/instructions/terraform-tests.instructions.md.tmpl` | `copilot/gcp/instructions/terraform-tests.instructions.md.tmpl` |
| `.github/instructions/*-configs.instructions.md` | `copilot/instructions/orchestration-configs.instructions.md.tmpl` | ← same | ← same |
| `.github/instructions/pipeline-templates.instructions.md` | `copilot/instructions/pipeline-templates.instructions.md.tmpl` | ← same | ← same |

#### For Claude Code — use templates from [./references/claude/](./references/claude/):

| Output File | Azure Template | AWS Template | GCP Template |
|-------------|---------------|--------------|--------------|
| `CLAUDE.md` | `claude/CLAUDE.md.tmpl` | `claude/aws/CLAUDE.md.tmpl` | `claude/gcp/CLAUDE.md.tmpl` |
| `.claude/commands/create-terraform-module.md` | `claude/commands/create-terraform-module.md.tmpl` | `claude/aws/commands/create-terraform-module.md.tmpl` | `claude/gcp/commands/create-terraform-module.md.tmpl` |
| `.claude/commands/create-{tool}-stack.md` | `claude/commands/create-orchestration-stack.md.tmpl` | ← same | ← same |
| `.claude/commands/create-infra-pipeline.md` | `claude/commands/create-infra-pipeline.md.tmpl` | ← same | ← same |

#### Cloud-Specific Placeholder Reference

When filling templates for non-Azure clouds, use these pre-resolved values:

**AWS placeholders:**

| Placeholder | AWS Value |
|-------------|-----------|
| `{{CLOUD_PROVIDER}}` | `AWS` |
| `{{PROVIDER_NAME}}` | `aws` |
| `{{PROVIDER_VERSION_CONSTRAINTS}}` | `aws = { source = "hashicorp/aws", version = ">=5.0,<6.0" }` |
| `{{PROVIDER_RESOURCE_EXAMPLE}}` | `aws_s3_bucket.default` |
| `{{LOCATION_ATTRIBUTE}}` | (omit — AWS resources use region from provider config) |
| `{{RESOURCE_GROUP_ATTRIBUTE}}` | (omit — AWS has no resource groups) |
| `{{DATA_SOURCE_OVERRIDE}}` | `override_data { target = data.aws_caller_identity.current, values = { account_id = "123456789012", arn = "arn:aws:iam::123456789012:root", user_id = "123456789012" } }` |
| `{{TEST_STANDARD_VARIABLES}}` | `prefix = "test-auto"`, `region = "us-east-1"`, `tags = {}`, `env_default_tags = { managed_by = "Terraform" }` |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_tags, var.tags)` |
| `{{AUTH_REQUIREMENTS}}` | OIDC via `aws-actions/configure-aws-credentials@v4` — no static credentials |
| `{{RESOURCE_IDENTIFIER}}` | `default` |
| `{{AWS_ACCOUNT_ID}}` | Target AWS account ID (e.g., `123456789012`) |
| `{{AWS_DEFAULT_REGION}}` | Default AWS region (e.g., `us-east-1`) |
| `{{STATE_BUCKET}}` | S3 bucket name for Terraform state |
| `{{STATE_KEY_PREFIX}}` | Key prefix in state bucket (e.g., `terraform/`) |
| `{{STATE_BUCKET_REGION}}` | Region of the S3 state bucket |
| `{{LOCK_TABLE}}` | DynamoDB table name for state locking |
| `{{TERRAFORM_ROLE_NAME}}` | IAM role name for Terraform OIDC auth |
| `{{NAME_ATTRIBUTE}}` | Resource name attribute (e.g., `name` for most AWS resources) |

**GCP placeholders:**

| Placeholder | GCP Value |
|-------------|-----------|
| `{{CLOUD_PROVIDER}}` | `GCP` |
| `{{PROVIDER_NAME}}` | `google` |
| `{{PROVIDER_VERSION_CONSTRAINTS}}` | `google = { source = "hashicorp/google", version = ">=5.0,<6.0" }` |
| `{{PROVIDER_RESOURCE_EXAMPLE}}` | `google_storage_bucket.default` |
| `{{LOCATION_ATTRIBUTE}}` | `location = var.region` (or `location = var.zone` for zonal resources) |
| `{{RESOURCE_GROUP_ATTRIBUTE}}` | `project = var.project_id` |
| `{{DATA_SOURCE_OVERRIDE}}` | `override_data { target = data.google_project.current, values = { project_id = "test-project-123", number = 123456789, name = "test-project" } }` |
| `{{TEST_STANDARD_VARIABLES}}` | `prefix = "test-auto"`, `project_id = "test-project-123"`, `region = "europe-west1"`, `labels = {}`, `env_default_labels = { managed_by = "terraform" }` |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_labels, var.labels)` (note: GCP uses `labels`, not `tags`) |
| `{{AUTH_REQUIREMENTS}}` | Workload Identity Federation via `google-github-actions/auth@v2` — no service account keys |
| `{{RESOURCE_IDENTIFIER}}` | `default` |
| `{{GCP_PROJECT_ID}}` | Target GCP project ID (e.g., `my-project-prod`) |
| `{{GCP_PROJECT_NUMBER}}` | GCP project number (e.g., `123456789`) |
| `{{STATE_BUCKET}}` | GCS bucket name for Terraform state |
| `{{STATE_KEY_PREFIX}}` | Key prefix in state bucket (e.g., `terraform/`) |
| `{{WIF_POOL}}` | Workload Identity Federation pool name |
| `{{WIF_PROVIDER}}` | Workload Identity Federation provider name |

#### Generation rules:
1. Only generate orchestration files if the workspace uses Terragrunt/Terramate/etc.
2. Adapt CI/CD templates to the actual platform (GitHub Actions/ADO/GitLab)
3. Use the cloud-specific template subdirectory (`aws/`, `gcp/`) for cloud-specific files; use base templates for shared files
4. Use actual module source URLs, not placeholders
5. Include real naming patterns discovered from the workspace
6. Skip files that already exist (warn and offer to merge)
7. If generating for both tools, ensure consistency between Copilot and Claude outputs
8. Save the maturity report as `maturity-report.md` in the workspace root using the template at `references/maturity-report.md.tmpl`

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
