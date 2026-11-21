---
name: pre-pr-check
description: Run the same checks as CI (template validation, bundle build, examples regeneration check, CLI tests, markdownlint) before opening a PR
disable-model-invocation: true
---

# Pre-PR check

Run the checks from `.github/workflows/validate.yml` locally, in CI order. Stop at the first failure, show its output, and fix it before continuing.

## Setup

Use a local virtualenv (gitignored):

```bash
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q pyyaml './cli[dev]'
```

## Checks

```bash
.venv/bin/python scripts/build_templates.py
.venv/bin/python scripts/validate_templates.py
.venv/bin/python scripts/build_examples.py --check
.venv/bin/pytest cli/tests/ -q
npx --yes markdownlint-cli2 --config .markdownlint.yml "**/*.md" "#node_modules" "#.venv"
```

## If a check fails

- `build_examples.py --check` fails: the templates or generator changed. Run `.venv/bin/python scripts/build_examples.py`, review the diff in `examples/generated/`, and commit it.
- `validate_templates.py` fails on the bundle comparison: run `build_templates.py` again. The bundle is gitignored and never edited by hand.
- markdownlint: match the glob and ignores to the `markdownlint` step in `validate.yml` if they have changed.

Report which checks passed and which failed. Do not claim success unless every check exited 0.
