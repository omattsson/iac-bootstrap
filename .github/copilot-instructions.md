# Copilot Instructions for iac-bootstrap

## Project Purpose

This repo is a **meta-tool**: it generates AI agent customization files (for VS Code Copilot and Claude Code) tailored to Terraform/IaC workspaces. It does NOT contain Terraform infrastructure itself — only templates, a CLI, and examples of generated output.

## Repository Structure

| Path | Purpose |
|------|---------|
| `SKILL.md` | Bootstrap procedure (Copilot skill entry point). Defines the 5-phase workflow. |
| `references/` | **Read-only** `.tmpl` template files with `{{PLACEHOLDER}}` syntax. Never modify these. |
| `cli/bootstrap_iac/` | Python CLI package: `cli.py` (Click entrypoint), `interview.py` (context builder), `generator.py` (template engine), `discovery.py` (workspace scanner), `validator.py` (output checker). |
| `cli/bootstrap_iac/templates/` | Bundled copy of templates shipped with the CLI package. Must stay in sync with `references/`. |
| `scripts/validate_templates.py` | CI validator: checks placeholder syntax, YAML frontmatter, example cleanliness, and SKILL.md references. |
| `examples/` | Fully-resolved example outputs (no `{{PLACEHOLDER}}` tokens should remain). |

## Key Conventions

### Template Placeholders

- Syntax: `{{UPPER_CASE_NAME}}` — always uppercase letters, digits, underscores, starting with a letter.
- Regex: `[A-Z][A-Z0-9_]*` — this is enforced by the CI validator.
- Lowercase placeholders like `{rule_name}` or `{resource}` are **not** template placeholders — they are Python `.format()` strings or documentation literals. Do not flag these.

### Template Files Are Read-Only

Files under `references/` and `cli/bootstrap_iac/templates/` with the `.tmpl` extension are templates. They intentionally contain `{{PLACEHOLDER}}` tokens. Do not suggest replacing these with concrete values.

### Cloud-Specific Template Overrides

The template engine checks for cloud-specific overrides at `{prefix}/{cloud}/{rest}` before falling back to the base template at `{prefix}/{rest}`. For example, `copilot/aws/copilot-instructions.md.tmpl` overrides `copilot/copilot-instructions.md.tmpl` for AWS workspaces.

### Example Files

Files under `examples/` are fully-resolved generated output. They should contain no `{{PLACEHOLDER}}` tokens. However, they may legitimately contain:
- GitHub Actions expressions: `${{ github.ref }}`, `${{ vars.TF_VERSION }}`
- Jinja/template expressions from CI platforms

## Terraform / HCL Domain Knowledge

This repo generates instructions that reference Terraform idioms. When reviewing:

- **`replace()` supports regex** — Terraform's `replace(string, substring, replacement)` supports regex patterns when the `substring` argument is wrapped in forward slashes: `replace(var.name, "/[^a-z0-9-]/", "")`. Do not suggest using `regexreplace()` instead — `replace()` with `/pattern/` is idiomatic and official.
- **`optional()` with defaults** — `optional(type, default)` in variable type constraints is valid HCL since Terraform 1.3.
- **`for_each` over `count`** — for feature toggles, both patterns are valid. `count = var.enable_x ? 1 : 0` is a standard pattern.

## VS Code Copilot Domain Knowledge

When reviewing generated Copilot customization files:

- **`applyTo` glob patterns** support brace expansion: `*.{tf,hcl}`, `*.{py,yaml,yml}`. This is standard VS Code glob syntax.
- **Frontmatter** in `.instructions.md` and `.agent.md` files uses YAML between `---` fences. Required field: `description`.

## Python CLI Conventions

- Python ≥ 3.9, dependencies: `click`, `pyyaml` (dev: `pytest`).
- Entry point: `bootstrap_iac.cli:main`.
- Tests are in `cli/tests/`. Run with `pytest cli/tests/`.
- The generator uses `dataclass`-based `OutputSpec` objects, not dicts.
- `build_context()` in `interview.py` maps lowercase discovery/interview keys to `UPPER_CASE` context keys consumed by the template engine.

## CI Pipeline

The GitHub Actions workflow (`.github/workflows/validate.yml`) runs:
1. **Template validation** (`scripts/validate_templates.py`) — 4 checks: placeholder syntax, YAML frontmatter, example cleanliness, SKILL.md references.
2. **Markdown lint** — only on `README.md`, `SKILL.md`, `CLAUDE.md`.
3. **CodeQL** — default security scanning.

## Review Guidelines

When reviewing changes to this repo:

1. **Don't flag `{{PLACEHOLDER}}` in `.tmpl` files** — they are intentional.
2. **Don't suggest adding type hints** to code that already works — the codebase uses type hints where they add clarity, not exhaustively.
3. **Check that `references/` and `cli/bootstrap_iac/templates/` stay in sync** — if a template is updated in one location, the other should match.
4. **Maturity score model** — gap severity definitions in `SKILL.md` are intentionally mutually exclusive: Critical covers Security/Testing/CI/CD; Moderate covers everything else.
5. **Orchestration support** — Terragrunt, Terramate, and Pulumi each have their own template variants and interview defaults. "None" means plain Terraform workspaces.
