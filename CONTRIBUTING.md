# Contributing to IaC Bootstrap

Thank you for your interest in contributing! This project thrives on community additions—new cloud providers, orchestration tools, CI platforms, and best practice patterns are all high-value contributions.

## Table of Contents

- [How to Propose Changes](#how-to-propose-changes)
- [Template File Conventions](#template-file-conventions)
- [Placeholder Naming Rules](#placeholder-naming-rules)
- [Adding a New Example](#adding-a-new-example)
- [PR Checklist](#pr-checklist)
- [Code of Conduct](#code-of-conduct)

---

## How to Propose Changes

**For small fixes** (typos, clarifications, minor template corrections):  
Open a pull request directly—no prior discussion needed.

**For larger additions** (new cloud provider support, new orchestration tool, new CI platform, major best practices updates):  
1. Open a GitHub Issue describing what you want to add and why.
2. Wait for a maintainer to acknowledge and provide feedback before starting work.
3. Once approved, fork the repo, make your changes, and submit a PR that references the issue.

Types of contributions that are especially welcome:
- New cloud provider templates (AWS, GCP, multi-cloud)
- Support for additional orchestration tools (Terramate, OpenTofu workspaces, Pulumi)
- Additional CI/CD platform templates (Azure DevOps, GitLab CI, Atlantis)
- New or updated best practice entries in `references/iac-best-practices.md`
- Improved or additional examples under `examples/`

---

## Template File Conventions

All output templates live under `references/copilot/` (VS Code Copilot) and `references/claude/` (Claude Code).

### Naming

| Type | Convention | Example |
|------|-----------|---------|
| Copilot instructions | `<name>.instructions.md.tmpl` | `terraform-modules.instructions.md.tmpl` |
| Copilot agent | `<name>.agent.md.tmpl` | `infra-architect.agent.md.tmpl` |
| Copilot skill | `<name>.skill.md.tmpl` | `create-terraform-module.skill.md.tmpl` |
| Copilot workspace instructions | `copilot-instructions.md.tmpl` | *(fixed name)* |
| Claude workspace instructions | `CLAUDE.md.tmpl` | *(fixed name)* |
| Claude command | `<name>.md.tmpl` | `create-terraform-module.md.tmpl` |

### Rules

- Templates **must** use the `.tmpl` extension—never commit a template without it.
- Templates **must not** contain hard-coded company names, account IDs, credentials, or cloud-specific resource names that should vary per workspace.
- Every variable part of a template **must** use a `{{PLACEHOLDER}}` token (see [Placeholder Naming Rules](#placeholder-naming-rules)).
- Keep templates tool-agnostic where possible; add cloud- or tool-specific sections under clearly labelled headings.
- Mirror the structure of existing templates when adding new ones to the same category.

---

## Placeholder Naming Rules

Placeholders use `SCREAMING_SNAKE_CASE` wrapped in double curly braces: `{{PLACEHOLDER_NAME}}`.

### General rules

1. **Be descriptive** — the name should make the expected value obvious (`{{COMPANY_NAME}}`, not `{{NAME}}`).
2. **Stay consistent** — if the same concept is used in multiple templates, use the *same* placeholder name everywhere.
3. **Lowercase variants** — when a lowercase form is needed (e.g., for CLI commands), append `_LOWER`: `{{ORCHESTRATION_TOOL_LOWER}}`.
4. **Block placeholders** — for multi-line HCL or YAML blocks, use a suffix that signals the content type:
   - `_PATTERN` for naming/path patterns
   - `_BLOCK` for full HCL/YAML blocks
   - `_DIAGRAM` for ASCII art
   - `_DESCRIPTION` for prose descriptions

### Documenting new placeholders

When you add a new placeholder, add a row to the **Template Placeholders** table in `README.md` under the appropriate section. Include:

| Column | What to put |
|--------|------------|
| Placeholder | The token exactly as it appears in the template |
| Example | A realistic example value |
| Description | One-sentence explanation |

---

## Adding a New Example

Examples live under `examples/`. Each example demonstrates the full output of the bootstrap procedure for a specific workspace configuration (cloud + orchestration tool).

### Steps

1. Create a subdirectory named `<cloud>-<orchestration>` (e.g., `aws-terragrunt`, `gcp-plain`).
2. Run the bootstrap procedure (see `SKILL.md`) against a representative workspace for that combination.
3. Copy the generated files into your new example directory, preserving the output structure:
   ```
   examples/<cloud>-<orchestration>/
   ├── .github/                  # Copilot output (if generated)
   │   ├── copilot-instructions.md
   │   ├── agents/
   │   ├── skills/
   │   └── instructions/
   ├── CLAUDE.md                 # Claude Code output (if generated)
   └── .claude/commands/
   ```
4. Replace any company-specific or sensitive values with generic placeholders (e.g., `example-corp`, `example.com`).
5. Update the **Repository Structure** section of `README.md` to list the new example directory.
6. Confirm the example files contain **no** hardcoded secrets, account IDs, or real resource names.

---

## PR Checklist

Before submitting a pull request, ensure all of the following are true:

- [ ] **Validation passes** — all `{{PLACEHOLDER}}` tokens in modified templates are documented in `README.md`
- [ ] **No unreplaced placeholders** — example files contain no raw `{{...}}` tokens
- [ ] **Example updated** — if you added or changed a template, the corresponding example(s) under `examples/` reflect the change
- [ ] **README updated** — new placeholders are added to the placeholder tables; new examples are listed in the repository structure
- [ ] **`SKILL.md` updated** — if the bootstrap procedure itself changes (new phases, new template mappings), update `SKILL.md`
- [ ] **No secrets** — no hard-coded credentials, account IDs, subscription IDs, or real resource names
- [ ] **Consistent naming** — new templates follow the [Template File Conventions](#template-file-conventions) and new placeholders follow the [Placeholder Naming Rules](#placeholder-naming-rules)
- [ ] **PR description** explains what was added/changed and why

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this standard. Please report unacceptable behavior to the repository maintainers via GitHub Issues.
