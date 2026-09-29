# Review Terraform PR

Review a Terraform pull request against the Acme Corp workspace conventions.

## Usage

Run with no argument to review the current branch against its pull request base, or pass a base ref, a PR number, or a path to narrow the review: `$ARGUMENTS`

## Before You Review

Read the workspace conventions first and let them override any general Terraform advice:

1. `CLAUDE.md` — workspace rules, naming, tagging, and module conventions
2. `.claude/commands/create-terraform-module.md` — the module shape this workspace expects
3. `.claude/commands/create-infra-pipeline.md` — pipeline structure
4. The orchestration command for Terragrunt, when the workspace uses one —
   skip this step if there is no orchestration layer

If `CLAUDE.md` contradicts this command, **`CLAUDE.md` wins** — say so in the report.

## Scope

`$ARGUMENTS` is optional. Interpret it before diffing, and apply what it asks for:

| `$ARGUMENTS` | Patch to review |
|--------------|-----------------|
| empty | `git diff "$BASE"...HEAD` |
| a base ref, e.g. `release/2.1` | use it as `$BASE`, then diff as above |
| a PR number, e.g. `123` | `gh pr diff 123` |
| a path, e.g. `modules/network` | resolve `$BASE`, then `git diff "$BASE"...HEAD -- <path>` |

Add `--name-only` to the same command when you just need the file list. Always read the
patch itself: for a PR number the local checkout may be a different branch entirely, so
the files on disk are not what that pull request changes.

Resolve `$BASE` whenever the argument does not supply one. Never assume `main`, because a
pull request may target a release or maintenance branch:

```bash
# The pull request's own base when one is checked out, else the repository default.
BASE="origin/$(gh pr view --json baseRefName --jq .baseRefName 2>/dev/null)" \
  || BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD)"
```

If neither resolves, ask which branch to compare against rather than guessing.

In scope: `*.tf`, `*.tfvars`, `*.tftest.hcl`, and Terragrunt `*.hcl` configs. Pipeline definitions under `.github/workflows` are in scope too.
Out of scope: disposable output only — lock files, `.terraform/`, `node_modules/`,
`vendor/`, and build artefacts. Committed generated infrastructure code stays in scope: a
Terramate `_generated_*.tf` file is exactly where a hand edit or generator drift shows up,
and section 7 depends on seeing it.

Review the patch, not the whole file. Read a full file only for context when the patch
alone does not tell you whether a line is correct. Every finding must land on a line the
patch touches — added, modified, or **deleted**. A deletion can be the defect: a removed
test, encryption setting, approval gate, or required tag is a regression, so cite the
base-side line number for it. A pre-existing problem on an untouched line is not this
pull request's, so mention it at most as an aside under **Consider**.

If no in-scope file changed, say so and stop.

## Review Checklist

Work through every category and report findings or "no issues" for each.

### 1. Naming compliance

The naming rules below are written in HCL terms and apply to Terraform files. The same
intent applies to Terragrunt sources — judge those by the tool's own idioms
under section 7, not by `locals.tf`.

- Resource names follow `name = "${var.prefix}-${local.resource_abbreviation}-${local.suffix}"` ({prefix}-{resource_abbreviation}-{suffix})
- New module directories use the `tf-module-{name}` prefix
- Names are computed in `locals.tf`, not inlined per resource
- No hardcoded environment or region strings inside a name

### 2. Tag and label strategy

As above, `merge(var.env_default_tags, var.tags)` is the Terraform form. Apply the same intent to
Terragrunt sources using the tool's own tagging idiom.

- Taggable resources carry `merge(var.env_default_tags, var.tags)`
- No resource replaces the merge with a bare literal map

### 3. Variable design

Applies to Terraform files only. Skip for non-Terraform sources; section 7 covers those.

- Optional attributes of an object variable use `optional(type, default)`, so callers
  set only what they care about; a variable that is not required declares a `default`
- Shared inputs come from `common.variables.tf` rather than being redeclared
- Every variable has a `description` and an explicit `type`
- No hardcoded account, subscription, or project identifiers
- Sensitive inputs marked `sensitive = true`

### 4. Test coverage

Applies to Terraform modules only.

- New or changed modules have matching tests under `tests/`
- Tests use `command = plan` with `mock_provider "azurerm" {}`
- New behaviour has an assertion; changed naming or tagging updates its test
- Test variables match the module interface, including `common.variables.tf` inputs

### 5. Security
- No secrets, tokens, connection strings, or keys in code or `.tfvars`
- Storage and network resources private by default; public access opt-in and justified
- Least-privilege access grants, no wildcard actions or principals
- Encryption at rest and in transit enabled where supported
- Authentication uses Managed Identity / OIDC; no static credentials introduced

### 6. Module structure

Applies to Terraform modules only. A Terragrunt program or config is judged by section 7 instead.

- `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, plus `locals.tf` when naming is computed
- `versions.tf` pins the provider constraints this workspace standardises on:

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">=4.0.0,<5.0.0"
    }
  }
}
```

- Outputs expose name and id; sensitive outputs marked
- No provider block inside a reusable module

### 7. Orchestration compliance

Module sources follow `git::https://github.com/acme/tf-module-{name}?ref={tag}`.

- Terragrunt configs under `infrastructure-config` follow the DRY hierarchy
- Shared values live in `_envcommon/` rather than repeated per component
- `terraform { source = ... }` pins a module version tag, never a branch
- Every `dependency` block declares realistic `mock_outputs` and
  `mock_outputs_allowed_terraform_commands`
- Component `terragrunt.hcl` carries only component-specific overrides

### 8. Pipeline standards
Platform: GitHub Actions. The workspace pipeline conventions are:

- Name: `{action}-{component}.yml` (e.g. `deploy-networking.yml`)
- Two-stage: plan (on PR) → apply (on merge to main, with environment protection)
- Use `concurrency:` to prevent parallel runs on the same stack

Check the change against them, and against the checks for this platform:

- Plan runs on every pull request; apply runs only on the protected branch
- The apply job requires an environment approval before it runs
- Authentication uses OIDC federation, not stored credentials
- The apply job consumes the plan artifact the plan job published
- A failing plan fails the job; no `continue-on-error` hides the exit code

## Verification

Where the workspace supports it, run:

```bash
terraform fmt -check -recursive
terragrunt validate
```

`terraform fmt -check` only reads and formats files, so it is safe on any pull
request. `terragrunt validate` is not: for this workspace it resolves and
initialises the module sources the pull request declares, which downloads and can
execute code the author controls. Run it only for a pull request from a trusted
branch, and skip it for an untrusted fork.

Report a command that cannot run as an observation, not as a finding against the author.

## Report Format

Group findings by severity, most severe first. Cite `file:line` and quote the convention applied.

```markdown
## Terraform PR Review

**Scope:** N files changed

### Blocking
- `modules/tf-module-example/main.tf:24` — Resource name is hardcoded.
  Convention: names follow `name = "${var.prefix}-${local.resource_abbreviation}-${local.suffix}"`, computed in `locals.tf`.
  Suggested: move the name into `locals.tf` and reference `local.name`.

### Should fix
- `modules/tf-module-example/variables.tf:10` — `tags` has no description.

### Consider
- Extract the repeated subnet block into a `for_each`.

### Verified
- Naming, tagging, and module structure follow the workspace conventions.
- Tests cover the new conditional resource.
```

Rules for the report:
- **Blocking** — breaks a stated convention, or introduces a security or correctness defect
- **Should fix** — a real but non-blocking deviation
- **Consider** — a suggestion the author may decline
- List a category with no findings under **Verified**, so the author knows it was checked
- Do not invent a convention the workspace has not stated
- Do not report formatting that `terraform fmt` already fixes
- Report findings; do not rewrite the author's code unless asked
