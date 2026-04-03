# Before & After: AI-Assisted IaC with Agent Customizations

Side-by-side comparison of common infrastructure tasks performed manually versus with AI agents bootstrapped by this tool. Use this in presentations, onboarding docs, or README pages to justify the investment in AI-assisted infrastructure workflows.

---

## Scenario 1: Add a New Terraform Module (Key Vault)

A developer needs to add a new Azure Key Vault Terraform module that follows all company conventions — correct file layout, naming, tagging, private endpoints, diagnostics, and tests.

### Without Agents — Manual

| # | Step | Notes |
|---|------|-------|
| 1 | Look up `azurerm_key_vault` provider docs | Switch context to Terraform registry |
| 2 | Create module directory (`tf-module-key-vault/`) | Manual mkdir |
| 3 | Write `main.tf` with provider + data sources | Copy-paste from another module, adjust |
| 4 | Write `key_vault.tf` with resource block | Check attribute names in docs |
| 5 | Write `locals.tf` with naming logic | Remember the team's prefix-type-suffix pattern |
| 6 | Write `variables.tf` with module-specific inputs | Think through all required inputs |
| 7 | Copy `common.variables.tf` from another module | Easy to forget or copy a stale version |
| 8 | Write `outputs.tf` — at minimum `name` and `id` | Easy to miss outputs consumers need |
| 9 | Write `versions.tf` with provider constraints | Check current pinning policy in other modules |
| 10 | Add private endpoint sub-resource | Repeat steps 3–6 for PE resource |
| 11 | Add diagnostic settings | Another resource, another mini-cycle |
| 12 | Write `tests/key_vault.tftest.hcl` | Look up test framework syntax |
| 13 | Add mock providers and data source overrides | Common source of test failures |
| 14 | Run `terraform test` — fix failures | Iterate 2–3 times on average |
| 15 | Run `terraform fmt` and `terraform-docs` | Often forgotten under time pressure |
| 16 | Peer review catches missed tag merge | Another iteration |

**Total: ~16 steps · 60–120 minutes · high error rate**

---

### With Agents — AI-Assisted

| # | Step | Notes |
|---|------|-------|
| 1 | Ask agent: *"Create a Key Vault module following our conventions"* | Agent reads `CLAUDE.md` / `.github/copilot-instructions.md` for all conventions |
| 2 | Review generated files — all 7 standard files scaffolded correctly | Naming, tagging, PEs, diagnostics, and tests all included |
| 3 | Push to PR | Agent output is already fmt-clean and doc-ready |

**Total: 3 steps · 5–10 minutes · consistent output every time**

### Time & Quality Summary

| Metric | Without Agents | With Agents | Improvement |
|--------|---------------|-------------|-------------|
| Steps | 16 | 3 | **−81%** |
| Time (median) | 90 min | 8 min | **−91%** |
| Convention errors | 3–5 per review | 0–1 | **−80%+** |
| Forgotten files | Common | Rare | ✅ |
| Test coverage | Inconsistent | Automatic | ✅ |

---

## Scenario 2: Add a New Environment Stack (Prod)

A team needs to promote a service from `staging` to `prod` — creating all Terragrunt component configs, wiring up dependencies, and setting environment-specific overrides.

### Without Agents — Manual

| # | Step | Notes |
|---|------|-------|
| 1 | Identify all components in `staging/` | Manual directory scan |
| 2 | Create `prod/` directory hierarchy | Mirror the staging folder tree |
| 3 | Copy `account.hcl` / `subscription.hcl` | Update account ID, location, tags |
| 4 | Copy component config for `networking` | Update CIDR ranges, env-specific vars |
| 5 | Copy component config for `key-vault` | Update access policies, naming |
| 6 | Copy component config for `app-service` | Update SKU, autoscale rules |
| 7 | Copy component config for each remaining component | Repeat for every component |
| 8 | Wire `dependency` blocks with correct relative paths | Path errors break `run-all plan` |
| 9 | Add `mock_outputs` for plan-time dependency resolution | Easy to omit, causes CI failures |
| 10 | Pin module versions for prod | Check which tags passed staging |
| 11 | Add `prevent_destroy = true` on stateful resources | Commonly forgotten on first pass |
| 12 | Update CI pipeline to include prod stage | Edit YAML, adjust approval gates |
| 13 | Run `terragrunt run-all plan` — fix path errors | Iterate on dependency wiring |
| 14 | Peer review — finds 2–3 copy-paste oversights | Another review cycle |

**Total: ~14 steps · 60–90 minutes · copy-paste error risk on every component**

---

### With Agents — AI-Assisted

| # | Step | Notes |
|---|------|-------|
| 1 | Ask agent: *"Create a prod stack mirroring staging. Use `prevent_destroy` on Key Vault and storage. Pin module versions to the tags that passed staging."* | Agent reads the Terragrunt stack-manager skill and workspace hierarchy |
| 2 | Review generated configs — directory tree, all deps, version pins, `prevent_destroy` all present | Agent applies the DRY hierarchy pattern from workspace instructions |
| 3 | Run `terragrunt run-all plan` to validate | Typically passes on first run |
| 4 | Push to PR | CI pipeline stage auto-generated |

**Total: 4 steps · 10–15 minutes · deterministic output**

### Time & Quality Summary

| Metric | Without Agents | With Agents | Improvement |
|--------|---------------|-------------|-------------|
| Steps | 14 | 4 | **−71%** |
| Time (median) | 75 min | 12 min | **−84%** |
| Dependency wiring errors | Frequent | Rare | ✅ |
| Missed `prevent_destroy` | Common | Never | ✅ |
| Version pin discipline | Inconsistent | Enforced | ✅ |

---

## Scenario 3: Debug a Failing Terraform Plan

A CI plan job fails with a cryptic provider error. The engineer needs to diagnose the cause, find the affected resource, and apply the correct fix without introducing regressions.

### Without Agents — Manual

| # | Step | Notes |
|---|------|-------|
| 1 | Read the CI log — identify the error message | Multi-screen scroll through pipeline output |
| 2 | Map error to a resource in the module | Requires familiarity with provider internals |
| 3 | Search provider changelog for breaking changes | Context-switch to GitHub / Terraform Registry |
| 4 | Identify which provider version introduced the change | Binary search through changelog entries |
| 5 | Check current version constraint in `versions.tf` | Sometimes pinned too loosely |
| 6 | Apply fix to affected resource | Edit HCL, re-run plan locally |
| 7 | Verify no other modules share the broken pattern | Grep across all modules |
| 8 | Update tests to cover the fixed behavior | Easy to skip under time pressure |
| 9 | Push fix — second CI run | Wait for another pipeline cycle |

**Total: ~9 steps · 30–90 minutes (highly variable)**

---

### With Agents — AI-Assisted

| # | Step | Notes |
|---|------|-------|
| 1 | Paste error into chat: *"Our plan is failing with this error — what's wrong and how do we fix it?"* | Agent reads workspace instructions for provider version constraints |
| 2 | Agent identifies root cause, affected file, and fix; cross-checks against other modules automatically | Uses file-scoped instructions to know the module conventions |
| 3 | Review and apply the suggested diff | Usually a 2–5 line change |
| 4 | Push fix | Plan passes on first retry |

**Total: 4 steps · 5–20 minutes · root cause identified immediately**

### Time & Quality Summary

| Metric | Without Agents | With Agents | Improvement |
|--------|---------------|-------------|-------------|
| Steps | 9 | 4 | **−56%** |
| Time (median) | 50 min | 12 min | **−76%** |
| Blast radius check | Manual / often skipped | Automatic | ✅ |
| Test update | Often skipped | Prompted by agent | ✅ |

---

## Aggregate Impact

Across the three scenarios above:

| Scenario | Manual Steps | Agent Steps | Manual Time | Agent Time |
|----------|-------------|-------------|-------------|------------|
| New module | 16 | 3 | 90 min | 8 min |
| New env stack | 14 | 4 | 75 min | 12 min |
| Debug failing plan | 9 | 4 | 50 min | 12 min |
| **Total** | **39** | **11** | **215 min** | **32 min** |

> **Average step reduction: ~72% (28 of 39 steps eliminated) · Average time reduction: ~85% (183 of 215 minutes saved)**

These numbers are based on observed team workflows. Your results will vary with team size, module complexity, and existing automation. The consistency and error-rate improvements compound over time — especially as the team scales and onboards new engineers.

---

## Why the Gains Are Durable

Agent customizations generated by this bootstrap tool embed your team's actual conventions — naming patterns, tagging strategy, test structure, dependency wiring — directly into the agent's context. This means:

- **New engineers onboard faster**: The agent acts as a pair programmer who already knows all the rules.
- **Convention drift is reduced**: Every scaffolded file comes out consistent, not just the ones written by senior engineers.
- **Reviews focus on logic, not style**: Reviewers stop correcting formatting, missing outputs, or forgotten `prevent_destroy` flags.
- **Knowledge isn't locked in individuals**: Tribal knowledge encoded in `.github/copilot-instructions.md` and `CLAUDE.md` is available to every team member.
