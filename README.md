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

### Option A — CLI tool (fastest)

Install and run the `bootstrap-iac` command directly in your IaC workspace:

```bash
# Clone the repo
git clone https://github.com/omattsson/iac-bootstrap.git ~/git/iac-bootstrap

# Install the CLI
pip install ~/git/iac-bootstrap/cli

# Run in your IaC workspace (interactive mode)
cd ~/my-iac-workspace
bootstrap-iac
```

The tool scans your workspace, pre-fills defaults, prompts for ~10 answers,
and writes all customisation files. See [cli/README.md](cli/README.md) for the
full CLI reference.

**Non-interactive / CI usage:**

```bash
bootstrap-iac \
  --company  "Acme Corp" \
  --cloud    azure \
  --module-prefix tf-module \
  --orchestration terragrunt \
  --ci-cd    github-actions \
  --org      acme \
  --target   both \
  --non-interactive
```

**Preview without writing:**

```bash
bootstrap-iac --dry-run
```

**Validate generated output:**

```bash
bootstrap-iac --validate
```

### Option B — VS Code Copilot

**User-level skill (available in all workspaces):**

```bash
# Clone the repo (replace with your fork URL)
git clone https://github.com/omattsson/iac-bootstrap.git ~/git/iac-bootstrap

# Symlink as a Copilot skill
ln -s ~/git/iac-bootstrap ~/.copilot/skills/bootstrap-infra-workspace
```

Then in any IaC workspace, ask Copilot:

> Use the bootstrap-infra-workspace skill to set up AI agent customizations for this workspace.

**One-time use with `@workspace`:**

Open this repo alongside your IaC workspace in VS Code, then ask Copilot to follow the procedure in `SKILL.md` against your IaC workspace.

### Option C — Claude Code

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
├── docs/
│   └── migration-guide.md                # Retrofitting existing workspaces with AI customizations
│
├── SKILL.md                              # Bootstrap procedure (Copilot skill entry point)
├── CLAUDE.md                             # Instructions for using this repo with Claude Code
├── .claude/commands/
│   └── bootstrap.md                      # Bootstrap as a Claude Code slash command
│
├── cli/                                  # bootstrap-iac CLI tool (pip-installable)
│   ├── pyproject.toml                    # Package metadata and entry points
│   ├── README.md                         # CLI usage reference
│   ├── bootstrap_iac/                    # Python package
│   │   ├── cli.py                        # Click CLI entry point
│   │   ├── discovery.py                  # Workspace auto-detection
│   │   ├── interview.py                  # Interactive prompts + context builder
│   │   ├── generator.py                  # Template engine + file generation
│   │   ├── validator.py                  # Unreplaced placeholder checker
│   │   └── templates/                    # Bundled template copies (incl. aws/, gcp/ variants)
│   └── tests/                            # CLI unit tests
│
├── references/
│   ├── iac-best-practices.md             # Universal IaC patterns (10 categories)
│   ├── maturity-report.md.tmpl           # Maturity assessment report template
│   │
│   ├── copilot/                          # VS Code Copilot output templates (Azure base)
│   │   ├── copilot-instructions.md.tmpl
│   │   ├── agents/
│   │   ├── skills/
│   │   ├── instructions/
│   │   ├── aws/                          # AWS-specific overrides
│   │   │   ├── copilot-instructions.md.tmpl
│   │   │   ├── agents/terraform-module-builder.agent.md.tmpl
│   │   │   ├── skills/create-terraform-module.skill.md.tmpl
│   │   │   └── instructions/
│   │   │       ├── terraform-modules.instructions.md.tmpl
│   │   │       └── terraform-tests.instructions.md.tmpl
│   │   └── gcp/                          # GCP-specific overrides
│   │       ├── copilot-instructions.md.tmpl
│   │       ├── agents/terraform-module-builder.agent.md.tmpl
│   │       ├── skills/create-terraform-module.skill.md.tmpl
│   │       └── instructions/
│   │           ├── terraform-modules.instructions.md.tmpl
│   │           └── terraform-tests.instructions.md.tmpl
│   │
│   └── claude/                           # Claude Code output templates (Azure base)
│       ├── CLAUDE.md.tmpl
│       ├── commands/
│       ├── aws/                          # AWS-specific overrides
│       │   ├── CLAUDE.md.tmpl
│       │   └── commands/create-terraform-module.md.tmpl
│       └── gcp/                          # GCP-specific overrides
│           ├── CLAUDE.md.tmpl
│           └── commands/create-terraform-module.md.tmpl
│
└── examples/
    ├── azure-terragrunt/                 # Complete example for Azure + Terragrunt
    ├── aws-terraform/                    # Complete example for AWS + Terraform
    └── gcp-github-actions/               # Example for GCP + GitHub Actions
```

## Cloud-Specific Templates

Templates support **Azure** (default), **AWS**, and **GCP**. The base templates in `copilot/` and `claude/` are Azure-oriented. For AWS and GCP, cloud-specific overrides live in subdirectories (`aws/`, `gcp/`) and are used automatically when the cloud provider is set.

### How variant selection works

1. The generator checks for a cloud-specific template (e.g., `copilot/aws/copilot-instructions.md.tmpl`).
2. If the cloud variant exists, it is used instead of the base template.
3. If no cloud variant exists, the base template is used with cloud-appropriate placeholder values.

Azure always uses the base templates directly (no `azure/` subdirectory).

### Which files have cloud-specific variants

| Output File | Azure | AWS | GCP |
|-------------|:-----:|:---:|:---:|
| `copilot-instructions.md` | base | `aws/` | `gcp/` |
| `agents/terraform-module-builder.agent.md` | base | `aws/` | `gcp/` |
| `skills/create-terraform-module/SKILL.md` | base | `aws/` | `gcp/` |
| `instructions/terraform-modules.instructions.md` | base | `aws/` | `gcp/` |
| `instructions/terraform-tests.instructions.md` | base | `aws/` | `gcp/` |
| `CLAUDE.md` | base | `aws/` | `gcp/` |
| `commands/create-terraform-module.md` | base | `aws/` | `gcp/` |
| All other files (agents, orchestration, pipelines, etc.) | base | base | base |

### Choosing a cloud provider

**CLI:**

```bash
bootstrap-iac --cloud aws    # Uses AWS template variants
bootstrap-iac --cloud gcp    # Uses GCP template variants
bootstrap-iac --cloud azure  # Uses base templates (default)
```

**Copilot / Claude Code:** Specify the cloud during the interview phase. The bootstrap procedure (`SKILL.md`) detects the provider from existing `.tf` files or asks you to confirm.

### Key differences between cloud variants

| Aspect | Azure | AWS | GCP |
|--------|-------|-----|-----|
| **Provider** | `azurerm` | `aws` | `google` |
| **Region variable** | `location` | `region` | `region` / `location` |
| **Account/project** | subscription (from data) | account ID (from data) | `project_id` (variable) |
| **Tags/labels** | `tags` | `tags` | `labels` (lowercase, max 63 chars) |
| **State backend** | Azure Blob Storage | S3 + DynamoDB | GCS |
| **Auth pattern** | Managed Identity / OIDC | IAM Roles via OIDC | Workload Identity Federation |
| **Private connectivity** | Private Endpoints | VPC Endpoints | Private Service Connect |
| **Data sources** | `azurerm_client_config` | `aws_caller_identity`, `aws_region` | `google_project`, `google_client_config` |
| **Output attributes** | `name`, `id` | `name`, `id`, `arn` | `name`, `id`, `self_link` |

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

### AWS-specific placeholders

These placeholders are used in AWS template variants or resolve to AWS-specific values:

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{PROVIDER_NAME}}` | `aws` | AWS Terraform provider name |
| `{{PROVIDER_RESOURCE_EXAMPLE}}` | `aws_s3_bucket.default` | Example AWS resource reference |
| `{{LOCATION_ATTRIBUTE}}` | *(omit)* | AWS resources use region from provider config |
| `{{RESOURCE_GROUP_ATTRIBUTE}}` | *(omit)* | AWS has no resource groups |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_tags, var.tags)` | AWS tag merge expression |
| `{{DATA_SOURCE_OVERRIDE}}` | `override_data { target = data.aws_caller_identity.current ... }` | AWS mock data sources in tests |
| `{{TEST_STANDARD_VARIABLES}}` | `prefix = "test-auto"`, `region = "us-east-1"` | AWS standard test variables |
| `{{AUTH_REQUIREMENTS}}` | OIDC via `aws-actions/configure-aws-credentials@v4` | AWS auth in CI/CD |
| `{{AWS_ACCOUNT_ID}}` | `123456789012` | Target AWS account ID |
| `{{AWS_DEFAULT_REGION}}` | `us-east-1` | Default AWS region |
| `{{STATE_BUCKET}}` | `my-terraform-state` | S3 bucket name for Terraform state |
| `{{STATE_BUCKET_REGION}}` | `us-east-1` | Region of the S3 state bucket |
| `{{LOCK_TABLE}}` | `terraform-locks` | DynamoDB table name for state locking |
| `{{TERRAFORM_ROLE_NAME}}` | `TerraformOIDCRole` | IAM role name for Terraform OIDC auth |

### GCP-specific placeholders

These placeholders are used in GCP template variants or resolve to GCP-specific values:

| Placeholder | Example | Description |
|-------------|---------|-------------|
| `{{PROVIDER_NAME}}` | `google` | GCP Terraform provider name |
| `{{PROVIDER_RESOURCE_EXAMPLE}}` | `google_storage_bucket.default` | Example GCP resource reference |
| `{{LOCATION_ATTRIBUTE}}` | `location = var.region` | GCP resource location attribute |
| `{{RESOURCE_GROUP_ATTRIBUTE}}` | `project = var.project_id` | GCP project attribute |
| `{{TAG_MERGE_PATTERN}}` | `merge(var.env_default_labels, var.labels)` | GCP label merge (uses `labels`, not `tags`) |
| `{{DATA_SOURCE_OVERRIDE}}` | `override_data { target = data.google_project.current ... }` | GCP mock data sources in tests |
| `{{TEST_STANDARD_VARIABLES}}` | `prefix = "test-auto"`, `project_id = "test-project-123"` | GCP standard test variables |
| `{{AUTH_REQUIREMENTS}}` | Workload Identity Federation via `google-github-actions/auth@v2` | GCP auth in CI/CD |
| `{{GCP_PROJECT_ID}}` | `my-project-prod` | Target GCP project ID |
| `{{GCP_PROJECT_NUMBER}}` | `123456789` | GCP project number |
| `{{STATE_BUCKET}}` | `my-terraform-state` | GCS bucket name for Terraform state |
| `{{WIF_POOL}}` | `github-pool` | Workload Identity Federation pool name |
| `{{WIF_PROVIDER}}` | `github-provider` | Workload Identity Federation provider name |

## Migration Guide

Already have 50+ modules and wondering whether to start over or add AI customizations incrementally? See the **[Migration Guide](docs/migration-guide.md)** for:

- A decision tree: bootstrap from scratch vs retrofit existing workspace
- Step-by-step: adding agents to an existing workspace
- How to encode existing conventions so agents don't contradict them
- Handling mixed naming/tagging patterns across module generations
- Gradual rollout strategy (start with 1 agent, expand over weeks)

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on adding new templates, best practices, cloud provider support, and more.

Quick summary:

1. Fork the repo
2. Add/modify templates in `references/`
3. Update `SKILL.md` if the procedure changes
4. Test by running the bootstrap against a real workspace
5. Submit a PR — see the [PR checklist](CONTRIBUTING.md#pr-checklist)

## License

MIT
