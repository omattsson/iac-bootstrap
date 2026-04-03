# IaC Bootstrap Repo

This repo contains templates and a procedure for generating AI agent customizations for infrastructure-as-code workspaces. It targets both VS Code Copilot and Claude Code.

## Key Files

- `SKILL.md` — The bootstrap procedure (also the Copilot skill entry point)
- `references/iac-best-practices.md` — Universal IaC patterns for gap analysis
- `references/copilot/` — VS Code Copilot output templates (`.tmpl` files with `{{PLACEHOLDER}}` syntax)
- `references/claude/` — Claude Code output templates (`.tmpl` files with `{{PLACEHOLDER}}` syntax)

## How to Use

When asked to bootstrap an IaC workspace, follow the procedure in `SKILL.md`. The procedure has 5 phases:

1. **Discovery** — scan the target workspace for Terraform modules, orchestration configs, pipelines
2. **Interview** — ask about company name, cloud provider, module patterns, CI/CD, auth, etc.
3. **Gap Analysis** — compare against `references/iac-best-practices.md`
4. **Generate** — fill templates from `references/copilot/` and/or `references/claude/` with actual values
5. **Validate** — verify output quality

## Rules

- Never modify template files (`.tmpl`) — they are read-only references
- Always replace ALL `{{PLACEHOLDER}}` values in generated output
- Do not hardcode secrets, account IDs, or credentials in generated files
- If a template section is N/A (e.g., orchestration for a workspace without Terragrunt), omit it
