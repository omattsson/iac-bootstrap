# Contributing to IaC Bootstrap

Thank you for your interest in contributing! This project grows through community additions — new cloud providers, orchestration tools, CI/CD platforms, and best practices are all high-value contributions.

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) code of conduct.

## How to Contribute

### Proposing New Templates or Best Practices

1. **Open an issue first** — describe what you want to add (e.g., AWS support, Pulumi orchestration, GitLab CI templates) and why.
2. **Discuss the approach** — maintainers may suggest how it fits into the existing structure before you start writing.
3. **Submit a PR** — once the approach is agreed upon, implement and submit.

### Adding or Modifying Templates

Templates live in `references/copilot/` (VS Code Copilot) and `references/claude/` (Claude Code).

#### File Conventions

- Template files use the `.tmpl` extension (e.g., `CLAUDE.md.tmpl`, `copilot-instructions.md.tmpl`). The mapping from template to output path is not always a simple suffix strip — for example, skill templates produce `.github/skills/<name>/SKILL.md`.
- Copilot agent templates: `references/copilot/agents/<name>.agent.md.tmpl`
- Copilot skill templates: `references/copilot/skills/<name>.skill.md.tmpl`
- Copilot instruction templates: `references/copilot/instructions/<name>.instructions.md.tmpl`
- Claude command templates: `references/claude/commands/<name>.md.tmpl`

#### Placeholder Naming Rules

All templates use `{{PLACEHOLDER}}` syntax. Follow these rules when adding new placeholders:

- Use `UPPER_SNAKE_CASE` inside double curly braces: `{{MY_PLACEHOLDER}}`
- Choose descriptive names that indicate the value's purpose: `{{CLOUD_PROVIDER}}`, not `{{CP}}`
- Add a `_LOWER` suffix for lowercase variants: `{{ORCHESTRATION_TOOL}}` / `{{ORCHESTRATION_TOOL_LOWER}}`
- Multi-line placeholders (HCL blocks, YAML blocks, diagrams) should be documented with their expected format
- Document every new placeholder in the **Template Placeholders** section of `README.md`

#### Adding Cloud-Specific Template Variants

Cloud-specific templates override the base (Azure) templates for AWS and GCP. They live in subdirectories:

- `references/copilot/aws/` and `references/copilot/gcp/` for Copilot templates
- `references/claude/aws/` and `references/claude/gcp/` for Claude templates

**When to create a cloud variant:**

- The template contains cloud-specific resource types, data sources, or provider patterns
- The template references cloud-specific naming conventions or constraints (e.g., GCP label restrictions)
- The template includes cloud-specific authentication, state backend, or networking patterns

**When NOT to create a cloud variant:**

- The template is cloud-agnostic (e.g., orchestration configs, CI/CD pipeline structure, best practices)
- The template uses only `{{PLACEHOLDER}}` tokens that are resolved to cloud-appropriate values by the context builder

**How to add a cloud variant:**

1. Create the variant file at the same relative path under the cloud subdirectory (e.g., `copilot/aws/agents/terraform-module-builder.agent.md.tmpl`)
2. Copy the file into `cli/bootstrap_iac/templates/` at the corresponding path
3. The generator automatically checks for cloud variants before falling back to base templates
4. Update the template selection table in `SKILL.md` Phase 4
5. Add any new cloud-specific placeholders to the README placeholder tables

### Adding a New Example

Examples live in `examples/` and show the fully rendered output for a specific cloud + orchestration combination.

1. Create a directory under `examples/` named `<cloud>-<orchestration>` (e.g., `aws-terragrunt`, `gcp-terraform-stacks`).
2. Include the complete generated output for both Copilot (`.github/`) and Claude Code (`CLAUDE.md`, `.claude/commands/`).
3. All `{{PLACEHOLDER}}` values must be replaced with realistic values — no placeholders should remain.
4. Follow the same directory structure as the existing `examples/azure-terragrunt/` example.

### Updating Best Practices

The best practices reference lives in `references/iac-best-practices.md`. When adding new practices:

- Place them under the appropriate existing category (1–10) or propose a new category in your issue.
- Write practices as actionable rules, not opinions.
- Include brief rationale for each practice.

### Updating the Bootstrap Procedure

If your change affects the bootstrap flow, update `SKILL.md` accordingly. The procedure has five phases: Discovery, Interview, Gap Analysis, Generate, and Validate.

## PR Checklist

Before submitting your pull request, verify the following:

- [ ] **No leftover placeholders** — all `{{PLACEHOLDER}}` values in examples are replaced with real values
- [ ] **Template changes are intentional** — you only modified `.tmpl` files in `references/` when those template changes are part of your PR
- [ ] **New placeholders documented** — any new `{{PLACEHOLDER}}` is listed in the README's Template Placeholders section
- [ ] **Examples updated** — if you changed templates, the corresponding example output reflects the change
- [ ] **README updated** — repository structure, placeholder tables, or quick-start instructions are updated if affected
- [ ] **SKILL.md updated** — bootstrap procedure is updated if the change affects the generation flow
- [ ] **No secrets or credentials** — no hardcoded secrets, account IDs, or credentials in any file
- [ ] **Tested against a real workspace** — you have run the bootstrap against an actual IaC workspace and verified the output

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b my-contribution`)
3. Make your changes following the conventions above
4. Test by running the bootstrap against a real workspace
5. Submit a pull request

## Questions?

Open an issue if you're unsure about anything. We're happy to help guide your contribution.
