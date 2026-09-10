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

Exit codes:

- `0` — no unreplaced placeholders remain.
- `1` — unreplaced placeholders were found.
- `2` — the requested path is missing or unreadable, or a directory scan hit a
  file it could not read. A missing or unreadable path is reported as an error,
  not a clean result, so a mistyped path never looks like a successful check.

Files with unsupported (for example binary) extensions are ignored.

### Inspect discovery (`--discover`)

Scan a workspace and print what discovery inferred, as JSON, without generating:

```bash
bootstrap-iac --workspace /path/to/repo --discover
bootstrap-iac --workspace /path/to/repo --discover --ignore-dir vendor
```

The output includes:

- `cloud_provider` — the primary provider (most signals), kept for
  compatibility, plus `cloud_providers` listing every provider detected. A
  multi-cloud workspace is reported, not collapsed to one.
- `signals` — the evidence behind each inferred value, each naming the file or
  signal it came from, so every value can be traced.

Discovery prunes a built-in list of directories (`.terraform`,
`.terragrunt-cache`, `.git`, `node_modules`, and similar). Add more with
`--ignore-dir` (repeatable). Pruning keeps scanning safe on large repositories.
Pipeline detection accepts both `.yml` and `.yaml`, and an empty
`.github/workflows/` is not treated as GitHub Actions.

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
| `--overwrite` | | Overwrite existing files and config (default: skip) |
| `--non-interactive` | | Never prompt — use defaults + flags only |
| `--validate PATH` | | Check for unreplaced placeholders |
| `--config PATH` | | Path to `.bootstrap-iac.yaml` config file (auto-detected if omitted) |
| `--save-config` | | Write interview answers after generation (to `--config` path or workspace) |
| `--check-config` | | Validate the config file and exit (0 valid, 1 invalid, 2 missing) |
| `--discover` | | Scan `--workspace` and print the discovery result as JSON, then exit |
| `--ignore-dir DIR` | | Skip a directory during discovery (repeatable; adds to the built-in ignore list) |
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

### Templates

`references/` at the repository root is the single source of truth for the
`.tmpl` templates. The bundled copy under `cli/bootstrap_iac/templates/` is
generated from it and is not tracked in git.

```bash
# Regenerate the bundled copy after editing references/
python scripts/build_templates.py

# Verify the bundled copy is up to date
python scripts/build_templates.py --check
```

The package build regenerates the bundle automatically when `references/` is
reachable from the build. A default `pip install ./cli` or `python -m build`
isolates the build to the `cli/` directory, so `references/` (a sibling of
`cli/`) is not reachable; the build then uses the `templates/` already present.

- Full checkout, non-isolated build (`references/` reachable): the bundle is
  regenerated automatically — no manual step.
- Isolated build, or packaging a standalone `cli/` tree without its repository
  siblings: run `python scripts/build_templates.py` first. On a fresh clone the
  bundle is absent, so a default `pip install ./cli` needs this step; otherwise
  the build fails with a clear message. CI runs the generator automatically.

## Config File

Commit a `.bootstrap-iac.yaml` (or `.bootstrap-iac.yml`) in your workspace root
for deterministic re-generation without re-answering prompts:

```yaml
version: "1"
company: Acme Corp
cloud: Azure
module_prefix: tf-module
orchestration: Terragrunt
orchestration_dir: infrastructure-config
ci_cd: GitHub Actions
auth: workload-identity
state_backend: azurerm
naming: "{prefix}-{resource_abbreviation}-{suffix}"
tag_strategy: merge(var.env_default_tags, var.tags)
standard_variables: |
  - `prefix` — Resource name prefix
  - `location` — Azure region
  - `resource_group_name` — Target resource group
  - `tags` — Resource-specific tags (map(string))
org: acme
target: both
```

**Supported keys:** `version`, `company`, `cloud`, `module_prefix`,
`orchestration`, `orchestration_dir`, `ci_cd`, `auth`, `state_backend`,
`naming`, `tag_strategy`, `standard_variables`, `org`, `target`. Each non-null
value is a scalar; a `null` value is treated as unset. `version` is optional;
the current schema version is `1`.

**Validation:**

- An unknown key (for example a typo such as `clould:`) is an error that names
  the offending key and lists the supported keys.
- An invalid `cloud`, `orchestration`, `ci_cd`, `target`, or `version` value is
  an error that names the key and the accepted values.
- A `null` value is treated as unset; a non-scalar value (list or mapping) is an
  error that names the key.
- Check a config without generating: `bootstrap-iac --check-config`. It exits
  `0` if valid, `1` if the config is invalid, and `2` if it is missing or
  unreadable.

**Precedence** (lowest to highest), for each value:

1. Workspace discovery defaults.
2. Config file values.
3. CLI flags (for example `--company`, `--cloud`).
4. Interactive prompts fill only values not set by the layers above.

**Behaviour:**

- Auto-detected in the workspace root (or specify with `--config path`).
- `bootstrap-iac --non-interactive` with a config file requires zero flags.
- Generate a config from your answers: `bootstrap-iac --save-config` (the saved
  file is stamped with `version: "1"`).

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOOTSTRAP_IAC_TEMPLATES_DIR` | Override the templates directory path |
