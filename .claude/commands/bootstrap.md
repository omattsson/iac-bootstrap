# Bootstrap IaC Workspace

Generate AI agent customizations for the current infrastructure-as-code workspace. Creates configuration files for **Claude Code** (`CLAUDE.md` + `.claude/commands/`) and optionally **VS Code Copilot** (`.github/` files).

## Argument
Describe target: `$ARGUMENTS`

## Procedure

Follow the full procedure from the bootstrap repo's `SKILL.md`. Summary:

### Phase 1: Discovery
Scan this workspace:
- Find Terraform modules: `find . -name "main.tf" -o -name "versions.tf"`
- Find orchestration: `find . -name "terragrunt.hcl" -o -name "root.hcl" -o -name "terramate.tm.hcl"`
- Find pipelines: `find . -name "*.yml" | head -20`
- Check existing customizations: `ls -la CLAUDE.md .claude/ .github/copilot-instructions.md 2>/dev/null`
- Read representative files to build a profile

### Phase 2: Interview
Ask the user about:
1. Company/org name
2. Cloud provider(s)
3. Module source pattern (Git URL)
4. Module prefix (tf-module-*, terraform-aws-*, etc.)
5. Orchestration tool (Terragrunt, Terramate, workspaces, none)
6. CI/CD platform
7. Auth pattern
8. State backend
9. Naming convention
10. Tag/label standard
11. Test framework
12. Standard variables
13. Target tool(s): Claude Code, VS Code Copilot, or both

### Phase 3: Gap Analysis
Compare workspace patterns against the best practices reference. Evaluate 10 areas (module design, naming, variables, testing, orchestration, CI/CD, security, code quality, state, rollout). Classify each as Adopted/Partial/Missing/N/A. Present as a table and ask which gaps to address.

Read the best practices from the bootstrap repo if available, or use embedded knowledge of IaC best practices.

### Phase 4: Generate Files

**For Claude Code**, generate:
- `CLAUDE.md` — combined workspace instructions, coding standards, and behavioral rules
- `.claude/commands/create-terraform-module.md` — module scaffolding command
- `.claude/commands/create-{tool}-stack.md` — stack management command (if applicable)
- `.claude/commands/create-infra-pipeline.md` — pipeline generation command

**For VS Code Copilot** (if requested), also generate:
- `.github/copilot-instructions.md`
- `.github/agents/*.agent.md`
- `.github/skills/*/SKILL.md`
- `.github/instructions/*.instructions.md`

Use templates from the bootstrap repo's `references/` directory as the base. Replace all `{{PLACEHOLDER}}` values with actual workspace values.

### Phase 5: Validate
- CLAUDE.md is self-contained (no broken references)
- No hardcoded secrets
- Slash commands match actual workspace patterns
- If Copilot files generated: `applyTo` patterns match real paths
