# Troubleshooting FAQ

Common setup and usage issues when working with the IaC Bootstrap tool.

---

## 1. Agent doesn't find my modules / wrong module picked

**Symptom:** The agent reports no modules found, or it references modules from the wrong directory.

**Solution:**
- Make sure your modules follow the expected layout: each module should contain a `main.tf` and/or `versions.tf`.
- During Phase 1 (Discovery), the agent searches for `**/main.tf` and `**/versions.tf`. If your modules live under an unusual path (e.g. `infra/modules/`), tell the agent explicitly: *"Modules are under `infra/modules/`, prefix `tf-module-`."*
- If the agent picks the wrong module, it may be matching on a root-level `main.tf` for a stack config. Move stack configs into an `orchestration/` or `infrastructure-config/` directory so they don't conflict with module discovery.
- Verify the `{{MODULE_PREFIX}}` placeholder was set correctly in the generated files — check `.github/copilot-instructions.md` or `CLAUDE.md` and update if needed.

---

## 2. Placeholder values don't look right after generation

**Symptom:** Generated files still contain `{{PLACEHOLDER}}` strings, or values like `{{COMPANY_NAME}}` appear literally in output files.

**Solution:**
- Run the bootstrap procedure again and review the interview answers. The agent replaces placeholders only when it has confirmed values for all of them.
- Check the [Template Placeholders](README.md#template-placeholders) section of the README for the full list of expected placeholders and example values.
- If only one or two placeholders are wrong, edit the generated file directly — search for `{{` to find any missed substitutions.
- If re-running, pass the missing values explicitly in the interview phase rather than accepting auto-detected defaults.

---

## 3. How do I customize the bootstrap interview?

**Symptom:** The default interview questions don't cover a convention specific to your workspace, or you want to skip questions that aren't relevant.

**Solution:**
- Edit `SKILL.md` (for Copilot) or `.claude/commands/bootstrap.md` (for Claude Code) and add or remove questions in the **Phase 2: Interview** section.
- To skip a question, remove it from the list. The corresponding placeholder in the templates will fall back to the default value or you can hard-code it in the template.
- To add a new question, add it to the interview list **and** add a matching `{{NEW_PLACEHOLDER}}` to any `.tmpl` files that need it under `references/copilot/` or `references/claude/`.
- Never edit `.tmpl` files directly in a production bootstrap — use them as read-only references and modify only the interview procedure.

---

## 4. Skills not showing up in Copilot

**Symptom:** After symlinking the repo as a Copilot skill, the `bootstrap-infra-workspace` skill doesn't appear when you reference it in VS Code.

**Solution:**
- Confirm the symlink target is correct:
  ```bash
  ls -la ~/.copilot/skills/bootstrap-infra-workspace
  ```
  It should point to the repo root (the directory containing `SKILL.md`), not to `SKILL.md` itself.
- Check that `SKILL.md` contains a valid YAML front-matter block at the top:
  ```yaml
  ---
  name: bootstrap-infra-workspace
  description: "..."
  ---
  ```
  Copilot uses the `name` field for skill discovery. If the front matter is malformed, the skill will be silently ignored.
- Reload the VS Code window (`Ctrl+Shift+P` → *Developer: Reload Window*) after creating or updating the symlink.
- Ensure the Copilot extension is up to date — skill support was added in a specific extension version. Check the VS Code Copilot changelog if the feature is unavailable.

---

## 5. Claude Code ignoring CLAUDE.md rules

**Symptom:** Claude Code does not follow the conventions written in `CLAUDE.md`, such as naming patterns or module layout rules.

**Solution:**
- `CLAUDE.md` must be present in the **root of the workspace** that Claude Code is opened in, not in a parent or sibling directory.
- Verify the file was generated to the correct location:
  ```bash
  ls -la CLAUDE.md
  ```
- Rules in `CLAUDE.md` are guidance, not hard constraints — Claude Code can still deviate if a request conflicts with a rule. Reinforce critical rules by adding them to individual slash commands in `.claude/commands/`.
- If Claude is operating on a specific subdirectory, add a second `CLAUDE.md` to that subdirectory with the subset of rules relevant to it.
- Check for syntax issues: CLAUDE.md is plain Markdown. Malformed headings or broken lists may cause sections to be skipped. Compare your file against `references/claude/CLAUDE.md.tmpl`.

---

## 6. How to update generated files after template changes

**Symptom:** The upstream templates in `references/` have been updated, but the generated files in your workspace are outdated.

**Solution:**
1. Pull the latest `iac-bootstrap` changes:
   ```bash
   cd ~/git/iac-bootstrap && git pull
   ```
2. Re-run the bootstrap procedure against your workspace. The agent will detect existing files and offer to merge or overwrite them (Phase 4, Generation Rule 6).
3. If you only need to update specific files, copy the relevant `.tmpl` file, manually replace all `{{PLACEHOLDER}}` values with your workspace's values, and overwrite the existing output file.
4. After updating, validate with Phase 5 checks: confirm no `{{PLACEHOLDER}}` strings remain, check `applyTo` patterns, and verify no secrets were introduced.
5. Commit the regenerated files to your IaC workspace repo so the team benefits from the updates.

---

## 7. Agent descriptions conflicting with each other

**Symptom:** When multiple agents are available (e.g. `infra-architect`, `terraform-module-builder`, `terraform-test-writer`), Copilot routes requests to the wrong agent, or agents give contradictory answers.

**Solution:**
- Each agent's `description` field is used for routing. Make descriptions specific and non-overlapping:
  - `infra-architect` — planning, design decisions, gap analysis
  - `terraform-module-builder` — writing and scaffolding module code
  - `terraform-test-writer` — writing `.tftest.hcl` files and test assertions
- If two agents have overlapping descriptions, edit the `.agent.md` files under `.github/agents/` and narrow the `description` to the exact trigger phrase.
- Add a `when:` or `use when:` note at the top of each agent's instructions to clarify to the model when it should take over.
- For Claude Code, agents are embedded in `CLAUDE.md` — ensure each role section has a distinct header and a clear scope statement so the model can self-select the right context.

---

## 8. How to add a custom cloud provider

**Symptom:** Your workspace uses a cloud provider not covered by the default templates (e.g. OCI, Alibaba Cloud, on-premises vSphere).

**Solution:**
1. Open the relevant template files under `references/copilot/` or `references/claude/`.
2. Identify provider-specific placeholders: `{{CLOUD_PROVIDER}}`, `{{PROVIDER_NAME}}`, `{{PROVIDER_BLOCK}}`, `{{PROVIDER_RESOURCE_EXAMPLE}}`, `{{LOCATION_ATTRIBUTE}}`, `{{RESOURCE_GROUP_ATTRIBUTE}}`.
3. During the bootstrap interview, provide your custom provider values when prompted. For example:
   - `{{CLOUD_PROVIDER}}` → `OCI`
   - `{{PROVIDER_NAME}}` → `oci`
   - `{{PROVIDER_BLOCK}}` → `oci = { source = "oracle/oci", version = ">=5.0.0,<6.0.0" }`
4. If the provider requires additional resource-level conventions not covered by existing placeholders, add new `{{CUSTOM_PLACEHOLDER}}` entries to the templates and extend the interview section in `SKILL.md` with questions to collect those values.
5. Verify the generated files reference the correct provider and resource syntax before committing them to your workspace.

---

## 9. Bootstrap takes too long / too many questions

**Symptom:** The interview phase asks many questions and the overall bootstrap takes a long time, especially for a simple workspace.

**Solution:**
- Use the `--non-interactive` flag (CLI mode) to skip the interview and rely on auto-detected values:
  ```bash
  bootstrap-iac --cloud azure --output-dir . --non-interactive
  ```
- Pre-answer questions by passing a config file or environment variables if supported by your version of the tool.
- For a minimal bootstrap (instructions only, no agents or skills), tell the agent: *"Generate only the workspace instructions file, skip agents and skills."*
- If the discovery phase is slow due to a large repo, point the agent at a specific subdirectory: *"Only scan modules under `infra/modules/`."*

---

## 10. Generated files committed with unreplaced placeholders

**Symptom:** A `git diff` or CI check shows `{{PLACEHOLDER}}` strings in committed output files.

**Solution:**
- Before committing, run a quick check for unreplaced placeholders:
  ```bash
  grep -rn '{{' .github/ CLAUDE.md .claude/ 2>/dev/null
  ```
  Any matches indicate placeholders that were not substituted.
- Add a pre-commit hook or CI step to catch this automatically:
  ```bash
  # .git/hooks/pre-commit (make executable with chmod +x)
  if grep -rqn '{{' .github/ CLAUDE.md .claude/ 2>/dev/null; then
    echo "ERROR: Unreplaced template placeholders found. Run bootstrap again."
    exit 1
  fi
  ```
- Re-run the bootstrap procedure, providing values for any placeholders that were left empty during the interview.
