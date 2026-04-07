# bootstrap-iac CLI

Interactive CLI tool that wraps the full [IaC Bootstrap](../) procedure:
**discover → interview → generate**.

## Installation

```bash
# From the repo root
pip install ./cli

# Or in development / editable mode
pip install -e ./cli
```

After installation the `bootstrap-iac` command is available on your `$PATH`.

## Quick Start

### Interactive mode (recommended)

Run in your IaC workspace and answer the prompts:

```bash
cd ~/my-iac-workspace
bootstrap-iac
```

The tool scans the workspace, pre-fills sensible defaults, and asks ~10
questions before generating all customisation files.

### Non-interactive / CI mode

Supply all values as flags:

```bash
bootstrap-iac \
  --company  "Acme Corp" \
  --cloud    azure \
  --module-prefix tf-module \
  --orchestration terragrunt \
  --orchestration-dir infrastructure-config \
  --ci-cd    github-actions \
  --org      acme \
  --target   both \
  --non-interactive
```

### Preview without writing (`--dry-run`)

```bash
bootstrap-iac --dry-run
# or with flags:
bootstrap-iac --company "Acme" --cloud azure --non-interactive --dry-run
```

### Check existing output (`--validate`)

Scan a directory (or file) for unreplaced `{{PLACEHOLDER}}` tokens:

```bash
bootstrap-iac --validate
bootstrap-iac --validate /path/to/workspace
bootstrap-iac --validate .github/copilot-instructions.md
```

Exits with code `0` if no placeholders remain, `1` otherwise.

## Options

| Flag | Short form | Description |
|------|------------|-------------|
| `--company NAME` | | Company / organisation name |
| `--cloud PROVIDER` | | Primary cloud: `azure` \| `aws` \| `gcp` |
| `--module-prefix PREFIX` | | Module directory prefix (e.g. `tf-module`) |
| `--orchestration TOOL` | | `terragrunt` \| `terramate` \| `pulumi` \| `none` |
| `--orchestration-dir DIR` | | Directory containing orchestration configs |
| `--ci-cd PLATFORM` | | `github-actions` \| `azure-devops` \| `gitlab-ci` \| `atlantis` |
| `--auth PATTERN` | | Authentication pattern description |
| `--state-backend BACKEND` | | Terraform state backend |
| `--naming PATTERN` | | Resource naming pattern |
| `--tag-strategy STRATEGY` | | Tagging / labelling strategy |
| `--org ORG` | | GitHub / ADO org (used in module source URLs) |
| `--target TARGET` | | `copilot` \| `claude` \| `both` (default: `both`) |
| `--workspace PATH` | | IaC workspace to scan (default: `.`) |
| `--output-dir PATH` | | Where to write files (default: `--workspace`) |
| `--dry-run` | | Preview without writing |
| `--overwrite` | | Overwrite existing files (default: skip) |
| `--non-interactive` | | Never prompt — use defaults + flags only |
| `--validate PATH` | | Check for unreplaced placeholders |
| `--config PATH` | | Path to `.bootstrap-iac.yaml` config file (auto-detected if omitted) |
| `--save-config` | | Write interview answers to `.bootstrap-iac.yaml` after generation |
| `--version` | `-V` | Show version and exit |
| `--help` | `-h` | Show help and exit |

## What Gets Generated

### VS Code Copilot (`.github/`)

| File | Purpose |
|------|---------|
| `.github/copilot-instructions.md` | Workspace-level instructions |
| `.github/agents/infra-architect.agent.md` | Planning & analysis agent |
| `.github/agents/terraform-module-builder.agent.md` | Module builder agent |
| `.github/agents/terraform-test-writer.agent.md` | Test writer agent |
| `.github/agents/{tool}-stack-manager.agent.md` | Orchestration agent (if applicable) |
| `.github/skills/create-terraform-module/SKILL.md` | Module scaffolding skill |
| `.github/skills/create-{tool}-stack/SKILL.md` | Stack management skill (if applicable) |
| `.github/skills/create-infra-pipeline/SKILL.md` | Pipeline generation skill |
| `.github/instructions/terraform-modules.instructions.md` | Module coding standards |
| `.github/instructions/terraform-tests.instructions.md` | Test coding standards |
| `.github/instructions/{tool}-configs.instructions.md` | Orchestration standards (if applicable) |
| `.github/instructions/pipeline-templates.instructions.md` | Pipeline standards |
| `.github/instructions/iac-best-practices.instructions.md` | Universal IaC best practices |

### Claude Code

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Combined workspace instructions + agents + rules |
| `.claude/commands/create-terraform-module.md` | Module scaffolding slash command |
| `.claude/commands/create-{tool}-stack.md` | Stack management slash command (if applicable) |
| `.claude/commands/create-infra-pipeline.md` | Pipeline generation slash command |

## Supported Combinations

| Cloud | Orchestration | CI/CD |
|-------|--------------|-------|
| Azure | Terragrunt, Terramate, Pulumi, None | GitHub Actions, Azure DevOps, GitLab CI, Atlantis |
| AWS | Terragrunt, Terramate, Pulumi, None | GitHub Actions, Azure DevOps, GitLab CI, Atlantis |
| GCP | Terragrunt, Terramate, Pulumi, None | GitHub Actions, Azure DevOps, GitLab CI, Atlantis |

## Development

```bash
# Install with dev extras
pip install -e "./cli[dev]"

# Run tests
cd cli
pytest
```

## Config File

Commit a `.bootstrap-iac.yaml` (or `.bootstrap-iac.yml`) in your workspace root
for deterministic re-generation without re-answering prompts:

```yaml
company: Acme Corp
cloud: azure
module_prefix: tf-module
orchestration: terragrunt
orchestration_dir: infrastructure-config
ci_cd: github-actions
auth: workload-identity
state_backend: azurerm
naming: "${var.prefix}-${var.resource_type}-${local.suffix}"
tag_strategy: merge(var.env_default_tags, var.tags)
org: acme
target: both
```

**Behaviour:**

- Auto-detected in the workspace root (or specify with `--config path`)
- Config values serve as defaults — CLI flags override them
- Interactive prompts skip values already provided by config
- `bootstrap-iac --non-interactive` with a config file requires zero flags
- Generate a config from your answers: `bootstrap-iac --save-config`

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOOTSTRAP_IAC_TEMPLATES_DIR` | Override the templates directory path |
