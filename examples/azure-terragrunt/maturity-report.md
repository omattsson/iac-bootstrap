# IaC Maturity Assessment — Contoso

**Workspace:** Azure infrastructure (Terraform modules + Terragrunt orchestration + Azure DevOps pipelines)  
**Assessed:** 2024-01-15  
**Assessor:** IaC Bootstrap — bootstrap-infra-workspace

---

## Overall Score

> **78% aligned with IaC best practices** (77.5 pts rounded)  
> 2 critical gap(s) · 2 moderate gap(s) · 6 strength(s)

| Rating | Score Range | Interpretation |
|--------|-------------|----------------|
| 🟢 Strong | 80–100% | Well-aligned; minor improvements possible |
| 🟡 Developing | 60–79% | Solid foundation; targeted improvements needed |
| 🟠 Foundational | 40–59% | Core practices in place; significant gaps remain |
| 🔴 Early | 0–39% | Major investment required across multiple areas |

**This workspace is rated: 🟡 Developing**

---

## Category Scores

| # | Category | Weight | Status | Points |
|---|----------|--------|--------|--------|
| 1 | Module Design | 15% | ✅ Adopted | 15/15 |
| 2 | Naming & Tagging | 10% | ✅ Adopted | 10/10 |
| 3 | Variable Design | 5% | ✅ Adopted | 5/5 |
| 4 | Testing | 15% | ✅ Adopted | 15/15 |
| 5 | Orchestration | 5% | ✅ Adopted | 5/5 |
| 6 | CI/CD | 15% | ⚠️ Partial | 7.5/15 |
| 7 | Security | 20% | ⚠️ Partial | 10/20 |
| 8 | Code Quality | 5% | ⚠️ Partial | 2.5/5 |
| 9 | State Management | 5% | ✅ Adopted | 5/5 |
| 10 | Progressive Rollout | 5% | ⚠️ Partial | 2.5/5 |
| | **Total** | **100%** | | **77.5/100** |

**Status key:** ✅ Adopted · ⚠️ Partial · ❌ Missing · — N/A

> **Scoring:** Adopted = full points · Partial = half points · Missing = 0 points · N/A = excluded and weight redistributed proportionally

---

## Critical Gaps

> Critical gaps carry significant risk or the highest remediation value. Address these first.
> **Definition:** Any Missing category, or a Partial status in Security, Testing, CI/CD, or Module Design (weight ≥ 15%).

### Security — Partial ⚠️

**What was found:** Modules do not consistently enforce `public_network_access_enabled = false` as the default. Several modules allow public access unless the caller explicitly disables it. No `checkov` rule enforces a private-by-default posture across the module library.

**Risk if unaddressed:** Resources may be accidentally exposed to the public internet. Compliance audits (ISO 27001, SOC 2) will flag publicly accessible endpoints. A single misconfigured module can create an attack surface across multiple environments.

**Remediation steps:**
1. Add `public_network_access_enabled = false` as the hardcoded or default-`false` value in every applicable module variable.
2. Require callers to explicitly set `public_network_access_enabled = true` with a documented justification comment in their Terragrunt config.
3. Add a `checkov` skip-list exception process so deviations are visible and auditable.
4. Add `CKV_AZURE_*` rules for public network access to the `.pre-commit-config.yaml` `checkov` hook.
5. Write a test assertion (`condition = output.public_network_access_enabled == false`) in each module's `security.tftest.hcl`.

**Estimated effort:** Medium — 2–3 hours per module, one-time configuration per CI pipeline.

---

### CI/CD — Partial ⚠️

**What was found:** The two-stage plan→apply pipeline is in place and identity-based authentication (MSI) is configured. However, no scheduled drift-detection pipeline exists. Infrastructure drift from manual changes or resource auto-healing is not detected until the next planned deployment.

**Risk if unaddressed:** Undetected drift accumulates silently. When drift is discovered during a deployment it causes plan failures, emergency rollbacks, and incident-level investigations. The longer drift goes undetected the harder it is to reconcile.

**Remediation steps:**
1. Add a scheduled Azure DevOps pipeline (e.g., nightly at 02:00 UTC) that runs `terragrunt run-all plan` across all environments.
2. Configure the pipeline to post a summary to a Teams/Slack channel when drift is detected (non-zero plan output).
3. Do **not** auto-apply drift — alert and require human review.
4. Store the drift detection pipeline template in `iac-pipeline-templates/` alongside existing templates.
5. Add a drift-detection pipeline `README` section explaining the alerting workflow.

**Estimated effort:** Small — 4–6 hours to implement and test the scheduled pipeline.

---

## Moderate Gaps

> Moderate gaps are worth addressing after critical items are resolved.
> **Definition:** Partial status in categories with weight < 15%.

### Code Quality — Partial ⚠️

**What was found:** `terraform_fmt` and `tflint` are configured in `.pre-commit-config.yaml`, but `terraform_docs` is not. Module `README.md` files are maintained manually, leading to documentation that quickly falls out of sync with actual variables and outputs.

**Remediation:** Add `terraform_docs` to the pre-commit configuration with a consistent `.terraform-docs.yaml` template. Run `pre-commit run --all-files` after adding it to backfill existing modules. Commit the generated `README.md` files as part of this change.

---

### Progressive Rollout — Partial ⚠️

**What was found:** The environment promotion pattern (dev → staging → prod) is implemented via Terragrunt with per-environment version pinning. However, `prevent_destroy = true` lifecycle rules are absent from critical resources (Key Vaults, Storage Accounts, databases). Accidental destruction of these resources is possible.

**Remediation:** Add `lifecycle { prevent_destroy = true }` to the primary resource in each module that manages a stateful or hard-to-restore resource. Pair with a module variable `var.prevent_destroy` (default `true`) so callers can override in non-production environments when needed.

---

## Strengths to Preserve

> These practices are well-established. Avoid regressions when making improvements.

- **Module Design** ✅ — Consistent file layout (`main.tf`, `locals.tf`, `variables.tf`, `common.variables.tf`, `outputs.tf`, `versions.tf`) across all modules. Resource identifier convention (`"default"`) and full-name override pattern are uniformly applied.
- **Naming & Tagging** ✅ — Name sanitization (`replace(var.suffix, "/[^0-9A-Za-z]+/", "-")`), length truncation (`substr`), and tag merge strategy (`merge(var.env_default_tags, var.tags)`) are consistently implemented. Required tags enforced at the orchestration layer.
- **Variable Design** ✅ — `common.variables.tf` is used as a shared contract across all modules. Terraform 1.3+ `optional()` is used for complex object defaults. Boolean feature toggles drive optional features via `count`.
- **Testing** ✅ — All tests use `command = plan` with `mock_provider`. Tests are organized by concern (`naming.tftest.hcl`, `tags.tftest.hcl`, `conditional.tftest.hcl`). All `common.variables.tf` variables are included in every test file.
- **Orchestration** ✅ — Terragrunt hierarchy is DRY with shared configs in `_envcommon/`. All `dependency` blocks include realistic `mock_outputs`. Module versions are pinned per environment in `subscription.hcl`.
- **State Management** ✅ — Remote state stored in Azure Blob Storage with encryption at rest. One state file per deployable component; no local state in shared environments.

---

## Recommended Next Actions

1. **[Critical] Enforce private-by-default in all modules** — Audit every module for `public_network_access_enabled` and similar attributes. Set secure defaults and add `checkov` enforcement to the pre-commit pipeline. Estimate: 1–2 sprints depending on module count.

2. **[Critical] Implement drift detection pipeline** — Add a nightly scheduled Azure DevOps pipeline that runs `terragrunt run-all plan --terragrunt-non-interactive` across all environments and alerts on non-zero output. Estimate: 1 sprint.

3. **[Moderate] Add `terraform_docs` to pre-commit** — Automate README generation so module documentation stays current without manual effort. Estimate: 1–2 days.

4. **[Moderate] Add `prevent_destroy` to stateful modules** — Protect Key Vaults, Storage Accounts, and databases from accidental deletion. Parameterize with `var.prevent_destroy` so non-production environments can still be torn down cleanly. Estimate: 1 day.

5. **[Sustain] Maintain test coverage as modules grow** — As new modules are added, enforce the test file conventions (`naming`, `tags`, `conditional`, `outputs` test files) via a CI check or code review checklist. Keep the mock provider pattern as the standard.

---

## Scoring Methodology

This report uses a weighted scoring model across 10 IaC practice areas:

| Category | Weight | Rationale |
|----------|--------|-----------|
| Security | 20% | Highest risk — data breaches and compliance failures |
| Testing | 15% | Reliability — catch regressions before they reach production |
| CI/CD | 15% | Deployment safety — prevents manual errors and unapproved changes |
| Module Design | 15% | Foundation — enables reuse and long-term maintainability |
| Naming & Tagging | 10% | Consistency — cost allocation and resource discoverability |
| Variable Design | 5% | Usability — ergonomics for module consumers |
| Orchestration | 5% | Efficiency — DRY configurations reduce configuration drift risk |
| Code Quality | 5% | Maintainability — reduces long-term technical debt |
| State Management | 5% | Reliability — prevents state corruption and data loss |
| Progressive Rollout | 5% | Deployment safety — blast radius reduction |

**Per-category score:**
- Adopted = 100% of category weight (full points)
- Partial = 50% of category weight (half points)
- Missing = 0% of category weight (zero points)
- N/A = category excluded; remaining weights renormalized to 100%

**Overall score** = sum of all earned category points, normalized to 100%

**Maturity ratings:**
- 🟢 Strong (80–100%): Best practices broadly followed; polish and sustain
- 🟡 Developing (60–79%): Solid foundation; address gaps methodically
- 🟠 Foundational (40–59%): Core practices present; significant improvement needed
- 🔴 Early (0–39%): Major investment required across multiple practice areas
