# Migration Guide: Retrofitting Existing IaC Workspaces

This guide helps teams with existing Terraform workspaces decide whether to bootstrap AI customizations from scratch or retrofit them incrementally, and walks through the step-by-step process for each approach.

## Greenfield vs Brownfield

| Scenario | Description |
|----------|-------------|
| **Greenfield** | New workspace with no existing modules, conventions, or agent config |
| **Brownfield** | Existing workspace with 1+ modules, established naming patterns, CI/CD pipelines, and possibly inconsistent conventions |

The bootstrap procedure in `SKILL.md` targets both scenarios, but brownfield workspaces require additional care to capture existing conventions without overwriting what already works.

---

## Decision Tree: Scratch vs Retrofit

```
Does the workspace have existing Terraform modules?
│
├─ NO → Bootstrap from scratch
│        Use SKILL.md Phase 1–5 in full.
│        All conventions are yours to define.
│
└─ YES → How consistent are the existing conventions?
          │
          ├─ CONSISTENT (same naming, tagging, file layout across modules)
          │   → Retrofit incrementally (see Step-by-Step below)
          │     Scan existing modules to extract conventions,
          │     then generate agent files that encode them.
          │
          ├─ MIXED (some modules follow patterns, others don't)
          │   → Retrofit with normalization notes
          │     Document both the target convention and the legacy pattern.
          │     Use agent instructions to guide new work toward target.
          │     See "Handling Mixed Patterns" section below.
          │
          └─ INCONSISTENT (no clear patterns)
              → Consider a hybrid approach:
                Pick the best existing patterns as the target standard,
                treat the rest as legacy, and bootstrap for new modules.
```

---

## Step-by-Step: Adding AI Agents to an Existing Workspace

### Step 1: Audit Existing Conventions

Before generating any files, scan your workspace to extract the patterns already in use. The bootstrap agent (Phase 1 of `SKILL.md`) automates this, but you can also do it manually:

```bash
# Find all module entry points
find . -name "main.tf" | sort

# Extract naming patterns from locals.tf files
grep -rE 'name\s*=' --include="locals.tf" -A 2 .

# Extract tag patterns
grep -rE 'tags\s*=' --include="locals.tf" -A 2 .

# Find existing variable files
find . \( -name "variables.tf" -o -name "*.variables.tf" \) | sort

# Check provider versions in use
grep -r 'required_providers' --include="versions.tf" -A 10 .
```

Document your findings before proceeding. The bootstrap interview (Phase 2) will ask for these values explicitly.

### Step 2: Run Bootstrap with an Existing-Workspace Mindset

When running the bootstrap procedure on an existing workspace, adapt Phase 2 (Interview) answers to reflect **what you already have** rather than what you want:

- **Naming pattern**: Extract from an existing `locals.tf`, e.g. `"${var.prefix}-kv-${local.suffix}"`
- **Tag merge pattern**: Extract from an existing `locals.tf`, e.g. `merge(var.env_default_tags, var.tags)`
- **Module source pattern**: Extract from an existing Terragrunt or root module reference
- **Standard variables**: List the variables that already appear across all modules (prefix, location, tags, etc.)

Using real values from existing code means the generated agent files will reinforce — not contradict — your current conventions.

### Step 3: Skip or Merge Existing Files

If any agent customization files already exist (e.g., a hand-written `.github/copilot-instructions.md`), do **not** overwrite them blindly. Bootstrap Phase 4 rule 6 applies:

> Skip files that already exist — warn and offer to merge.

To merge manually:
1. Open the existing file alongside the generated template output.
2. Preserve any custom sections your team has already written.
3. Add the generated sections that are missing.
4. Remove any contradictions between the old and new content.

### Step 4: Start with One Agent

Rather than generating all agent files at once, start with the agent most likely to be used immediately:

| Team Activity | Start With |
|---------------|------------|
| Creating new Terraform modules | `terraform-module-builder` agent |
| Writing tests for existing modules | `terraform-test-writer` agent |
| Planning infra changes | `infra-architect` agent |
| Managing Terragrunt stacks | `*-stack-manager` agent |

Enable one agent, let the team use it for 1–2 weeks, collect feedback, then add the next one. See the [Gradual Rollout Strategy](#gradual-rollout-strategy) section for details.

### Step 5: Reference Existing Conventions in Instructions

In the generated `.github/copilot-instructions.md` or `CLAUDE.md`, add a section that explicitly names your existing patterns. Example:

```markdown
## Existing Conventions (Do Not Change Without Discussion)

- **Module naming prefix**: `tf-module-*` (e.g., `tf-module-key-vault`)
- **Resource identifier**: always `default` for single-instance resources
- **Standard variables file**: `common.variables.tf` — copy verbatim across modules
- **Naming pattern**: `"${var.prefix}-${local.resource_code}-${local.suffix}"`
- **Tag merge**: `merge(var.env_default_tags, var.tags)` — always use this form
- **State backend**: Azure Blob Storage, one container per environment
```

This prevents the AI from "helpfully" renaming things or introducing new patterns that conflict with the existing 50+ modules.

---

## Handling Mixed Naming/Tagging Patterns

In long-lived workspaces, you often have multiple generations of conventions:

| Generation | Naming Pattern | Tag Strategy |
|------------|---------------|--------------|
| Legacy (2019–2021) | `company-env-resource` | Hard-coded tags per resource |
| Current standard | `prefix-type-suffix` | `merge(var.env_default_tags, var.tags)` |
| In-migration modules | Mix of both | Partially migrated |

### Recommended Approach

1. **Document both patterns in the instructions file.** Don't pretend the legacy pattern doesn't exist.
2. **Designate the target standard.** New modules always use the current standard.
3. **Flag legacy modules explicitly.** Add a comment in the instructions:

```markdown
## Naming Conventions

### Target Standard (use for all new modules)
Pattern: `"${var.prefix}-${local.resource_code}-${local.suffix}"`
Example: `"prod-kv-payments"`

### Legacy Pattern (existing modules only — do not introduce in new work)
Pattern: `"${var.company}-${var.env}-${var.resource_type}"`
Modules: tf-module-storage, tf-module-networking (pre-2022)
```

4. **Use the gap analysis (Phase 3) to track migration progress.** Mark naming as `Partial` and add a note about which modules still use the legacy pattern.
5. **Don't block on full migration.** Generate AI agents that follow the target standard. As legacy modules are touched for other reasons, migrate their naming then.

---

## Gradual Rollout Strategy

### Phase 0: Foundations (Week 1)

Generate only the workspace-level instructions file — no agents yet:

- VS Code Copilot: `.github/copilot-instructions.md`
- Claude Code: `CLAUDE.md`

This gives the AI context about your stack without changing any workflows. Let the team ask questions and refine the content for a week before enabling automation.

### Phase 1: First Agent (Weeks 2–4)

Enable the single agent that delivers the most immediate value for your team. For most teams with 50+ modules, this is the **module builder** agent — it prevents drift when creating new modules.

Checklist before enabling:
- [ ] Workspace instructions reviewed and approved by the team
- [ ] Naming and tagging conventions documented and agreed upon
- [ ] At least two team members have read the agent file and understand what it will do
- [ ] A test module has been created using the agent and reviewed manually

### Phase 2: Testing Support (Weeks 5–8)

Add the **test writer** agent. By now, the team is comfortable with AI-generated modules — test generation is a natural next step.

Checklist:
- [ ] Test framework documented in workspace instructions (native Terraform test, Terratest, or both)
- [ ] Standard variables for tests documented (those that appear in every test file)
- [ ] One manually written test reviewed alongside the agent output to verify consistency

### Phase 3: Planning and Orchestration (Weeks 9–12)

Add the **infra-architect** agent and (if applicable) the orchestration stack manager.

Checklist:
- [ ] Infra-architect agent scoped to read-only operations initially
- [ ] Orchestration configs (Terragrunt HCL etc.) documented in instructions
- [ ] Stack manager tested against a non-production environment first

### Phase 4: Skills and Commands (Month 4+)

Add scaffold skills (VS Code Copilot) or slash commands (Claude Code) for one-shot module and pipeline generation.

Checklist:
- [ ] All previous agents stable and providing consistent output
- [ ] Module scaffold reviewed against 3+ real modules to verify accuracy
- [ ] Pipeline template validated against actual CI/CD platform syntax

---

## Frequently Asked Questions

**Q: We have 50+ modules. Do we need to retrofit them all?**

No. You only need to document your conventions in the agent instructions. Existing modules don't need to be changed. New modules created with AI assistance will follow the documented conventions, and the agent can flag deviations if asked.

**Q: Our team uses different editors (some VS Code, some IntelliJ with Claude). Which tool should we generate for?**

Generate for both. The bootstrap procedure supports generating Copilot and Claude output simultaneously, and the conventions should be consistent across both. Start with whichever tool the majority of your team uses, then add the other.

**Q: We already have a hand-written `copilot-instructions.md`. Should we replace it?**

No — merge it. Your existing file likely contains tribal knowledge that isn't in any template. Run the bootstrap, take the generated output, and manually merge it with your existing file, keeping whichever content is more specific and accurate.

**Q: How do we handle modules owned by different teams with different conventions?**

Keep workspace-wide guidance in `.github/copilot-instructions.md`, and add team-scoped `.github/instructions/<team>.instructions.md` files with `applyTo` patterns for each team's directory (VS Code Copilot). For Claude Code, use path-scoped `CLAUDE.md` files in the relevant directories. This lets each team maintain their own conventions without conflicting.

**Q: What if the gap analysis shows we're missing many best practices?**

Don't try to close all gaps at once. Use the gap analysis to prioritize: focus on gaps that affect correctness and security first (naming safety, state encryption, secret handling), then consistency gaps (tag strategy, common vars), and finally quality gaps (pre-commit hooks, auto-docs). The AI agents themselves can help close some gaps incrementally as modules are updated.
