---
name: new-template
description: Add a new .tmpl template (Copilot or Claude Code) and wire it into SKILL.md, the examples and the CLI bundle
disable-model-invocation: true
argument-hint: <target: copilot|claude> <path under references/> <purpose>
---

# Add a new template

Arguments: `$ARGUMENTS`

New `.tmpl` files are intentional template changes, so the edit hook will ask for confirmation. Approve it, or run with `IAC_ALLOW_TMPL_EDIT=1`.

## Steps

1. **Pick the location.** Copilot templates go under `references/copilot/`, Claude Code templates under `references/claude/`. Cloud-specific variants go in the `aws/` or `gcp/` subtree. If the template has variants, add every variant, not only one.
2. **Write the template** following a sibling template's structure, comment density and frontmatter. Rules:
   - Placeholders are `{{UPPER_SNAKE_CASE}}` only (`validate_templates.py` enforces this).
   - Agent and instruction templates need valid YAML frontmatter.
   - No secrets, account IDs or credentials.
   - Sections that may not apply to a workspace must be omittable, as `CLAUDE.md` describes.
3. **Wire it in.** Reference the template from `SKILL.md` (the validator checks every referenced template exists). Check `cli/bootstrap_iac/generator.py` and `cli/bootstrap_iac/config.py` for how templates are selected, and add the new one there if needed. Update the README and FAQ file lists if they enumerate templates.
4. **Examples.** If a reproducible example under `examples/generated/` should include it, regenerate with `python scripts/build_examples.py` and review the diff.
5. **Tests.** Add or update cases in `cli/tests/` (`test_generator.py`, `test_generation_matrix.py`).
6. **Changelog.** Add an entry to `CHANGELOG.md`.
7. **Verify** by running the `/pre-pr-check` skill.
